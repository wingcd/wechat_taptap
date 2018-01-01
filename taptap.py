import os
import cv2
import numpy as np
import math
import time
import threading
import copy

runnding = False
imgfilename = "./screenshot.jpg"
width = 0
height = 0
#新模块顶点的偏移位置
offset = [3,5]
#与距离相乘的经验参数
magicnumber = 5.496 #for 1920*1080
#裁剪范围
clipSale = [0.171875, 0.11458]
clip = [0,0]
#开始按钮位置
startBtnPosScale = [0.5,0.82]
startBtnPos = [0,0]

def init():
    global magicnumber
    global clip,clipSale
    global startBtnPos,startBtnPosScale
    global height,width
    snapshot()
    if not os.path.exists(imgfilename):
        print("不支持adb截屏，请先开启开发者选项，并开启模拟点击！")
        return        

    image=cv2.imread(imgfilename)
    height,width = image.shape[:2]

    magicnumber = magicnumber * height / 1920
    clip[0] = int(clipSale[0]*height) 
    clip[1] = int(height - clipSale[1]*height)
    startBtnPos[0] = int(startBtnPosScale[0]*width)
    startBtnPos[1] = int(startBtnPosScale[1]*height)

def adb(args):
    os.system('adb ' + args)

def snapshot():
    adb("shell /system/bin/screencap -p /sdcard/screenshot.jpg")
    cp = "pull /sdcard/screenshot.jpg " + imgfilename
    adb(cp)

def swipe(duration):
    global startBtnPos
    duration = int(duration)
    cmd = "shell input swipe "+str(startBtnPos[0])+" "+str(startBtnPos[1])+" "+str(startBtnPos[0])+" "+str(startBtnPos[1])+ " " + str(duration)
    adb(cmd)

def ready():
    global image
    image=cv2.imread(imgfilename)
    #裁剪图片
    image=image[clip[0]:clip[1],0:width]
    #缩放图片，减少计算量

    #设置左右两边一定范围为背景色，减少后续处理错误
    h, w = image.shape[:2]
    color = image[0][0]

    ext = 50
    #左
    image[:,0:ext] = color[:]
    #右
    image[:,w-ext:w] = color[:]

    h = image.shape[1]/4
    w = image.shape[0]/4
    image=cv2.resize(image,(h,w),interpolation=cv2.INTER_CUBIC)

    return image

#通过模板，找出角色的位置,并将角色覆盖为背景色
def findRole():
    global image
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    template = cv2.imread("./temp.png",0)
    w,h = template.shape[::-1]
    
    method = cv2.TM_SQDIFF
    res = cv2.matchTemplate(gray,template,method)  
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)  
  
    if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:  
        top_left = min_loc  
    else:  
        top_left = max_loc  
    bottom_right = (top_left[0] + w, top_left[1] + h)
  
    c = image[top_left[1]][top_left[0]]
    color = np.array((int(c[0]),int(c[1]),int(c[2])))
    image[bottom_right[1]:top_left[1],top_left[0]:bottom_right[0],0] = 0
    cv2.rectangle(image,top_left, bottom_right, color, cv2.FILLED)  

    x0 = (bottom_right[0] - top_left[0]) / 2 + top_left[0]
    y0 = bottom_right[1]

    return x0,y0 - 5

#设置标志颜色，泛红区为黑色，其他为白色
def fillFlags(image):
    h = image.shape[0]
    w = image.shape[1]
    for x in range(0,w):
        for y in range(0,h):
            val = image[y][x]
            if val[0] != 255 or val[1] != 0 or val[2] != 0:
                image[y][x] = (255,255,255)
            else:
                image[y][x] = (0,0,0)

def findTable():
    global image,offset
    h, w = image.shape[:2]
    #进行滤波去掉噪声
    blured = cv2.blur(image,(2,2))    
    mask = np.zeros((h+2, w+2), np.uint8)
    #进行泛洪填充(填充纯红色，游戏中几乎没有红色)
    cv2.floodFill(blured, mask, (0,0), (255,0,0), (4,4,4),(4,4,4), 8)
    #设置为纯色
    fillFlags(blured)
    #得到灰度图
    gray = cv2.cvtColor(blured,cv2.COLOR_BGR2GRAY)
    #求二值图
    ret, binary = cv2.threshold(gray,220,255,cv2.THRESH_BINARY)
     #找到轮廓
    _,contours, hierarchy = cv2.findContours(binary,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE) 
    #绘制轮廓
    cv2.drawContours(image,contours,-1,(0,0,255),1)

    index = 0
    font = cv2.FONT_HERSHEY_SIMPLEX
    min = 99999
    y1 = 0
    x1 = 0
    for contour in contours:
        index = index+1
        topmost = tuple(contour[:,0][contour[:,:,1].argmin()])  
        rightmost = tuple(contour[:,0][contour[:,:,0].argmax()]) 

        cv2.putText(image,str(topmost[0]) + "," + str(topmost[1]),topmost, font, 0.3,(255,255,0),1,cv2.LINE_AA)
        cv2.putText(image,str(rightmost[0]) + "," + str(rightmost[1]),rightmost, font, 0.3,(255,255,0),1,cv2.LINE_AA)

        if topmost[1] > 10 and min > topmost[1]:
            min = topmost[1]
            x1 = topmost[0] + offset[0]
            y1 = topmost[1] + offset[1]

    return x1,y1

def calcDuration(x0,y0,x1,y1):
    global magicnumber

    dist = math.sqrt((x1-x0)*(x1-x0) + (y1-y0)*(y1-y0))
    return dist * magicnumber  #5.18 #

def draw(x0,y0,x1,y1):
    cv2.line(image, (x0, y0), (x1, y1),  (0,255,0), 1)
    cv2.circle(image,(x0, y0), 2, (255,255,0), -1)
    cv2.circle(image,(x1, y1), 2, (255,255,0), -1)

    cv2.imwrite("./saveimg.jpg",image)

def run():
    global runnding
    init()
    while(runnding):
        snapshot()
        ready()
        x0,y0 = findRole()
        x1,y1 = findTable()
        duration = calcDuration(x0,y0,x1,y1)
        swipe(duration)

        draw(x0,y0, x1, y1)
        time.sleep(2)

def debug():
    init()
    snapshot()
    ready()
    findRole()

    cv2.imshow("img", image)

runnding = True
#debug()
threading.Thread(target = run).run()
cv2.waitKey(0)
runnding = False

