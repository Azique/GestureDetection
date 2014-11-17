import cv2
import numpy as np
import time
import math

class GestureTemplate(object):
    def __init__(self, points, name = ""):
        self.points = np.array(points, dtype = np.float)
        self.points = GestureTemplate.normalizePoints(self.points)
        self.templateDistance = GestureTemplate.curveDistance(self.points)
        self.name = name

    @staticmethod
    def curveDistance(points):
        distance = 0
        for i in xrange(len(points)-1):
            distance += (abs(points[i][0] - points[i+1][0]) ** 2 + abs(points[i][1] - points[i+1][1]) ** 2) ** 0.5
        return distance

    @staticmethod
    def normalizePoints(points):
        return points - points[0]

    def compareGesture(self, gesturePoints):
        # First scale the input gesture based on the distance between points
        gesturePoints = gesturePoints[:-2]
        gesturePoints = np.array(gesturePoints, dtype = float)
        gesturePoints = GestureTemplate.normalizePoints(gesturePoints)
        # print "Normalized Gesture Points:", gesturePoints
        gestureDistance = GestureTemplate.curveDistance(gesturePoints)
        scaleFactor = self.templateDistance / gestureDistance
        gesturePoints *= scaleFactor
        # print "Template:", self.points
        # print "Template Distance:", self.templateDistance
        # print "Gesture Distance:", gestureDistance
        # print "Scale Factor:", scaleFactor
        # print "Adjusted Gesture Points:", gesturePoints
        # Both the template and the gesture will have (0, 0) for their start point
        # so that can be safely ignored
        # Directly map the indices of the gesture to the template
        totalError = 0
        for i in xrange(0, len(gesturePoints)):
            selfIndex = int(i * (len(self.points) - 1) / float((len(gesturePoints) -1)))
            # print i, self.points[selfIndex], gesturePoints[i]
            totalError += GestureTemplate.error(self.points[selfIndex], gesturePoints[i])
        # print totalDistanceDiff
        # print totalDistanceDiff/self.templateDistance
        return totalError/self.templateDistance

    @staticmethod
    def error(point1, point2):
        return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)

class HandProcessor(object):
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cameraWidth = 1920
        self.cameraHeight = 1080
        self.cap.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, self.cameraWidth)
        self.cap.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, self.cameraHeight)
        self.handCenterPositions = []
        self.stationary = False
        self.record = False
        self.endGesture = False
        self.gesturePoints = []
        self.initGestureTemplates()
        
    def initGestureTemplates(self):
        self.gestureTemplates = []
        hLineLR = GestureTemplate([(-x, 0) for x in xrange(100)],
            name="Horizontal Line Right to Left")
        self.gestureTemplates.append(hLineLR)
        hLineRL = GestureTemplate([(x, 0) for x in xrange(100)],
            name="Horizontal Line Left to Right")
        self.gestureTemplates.append(hLineRL)
        # let's try something more complicated, like a circle:
        circlePoints = [(10*math.cos(t), 10*math.sin(t)) for t in np.linspace(0, 2*math.pi, num=100)]
        ccwCircle = GestureTemplate(circlePoints, name="CCW Circle")
        self.gestureTemplates.append(ccwCircle)

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()

    # http://stackoverflow.com/questions/19363293/whats-the-fastest-way-to-increase-color-image-contrast-with-opencv-in-python-c
    @staticmethod
    def boostContrast(img):
        maxIntensity = 255.0
        phi = 1
        theta = 1
        boosted = (maxIntensity / phi) * (img/(maxIntensity/theta)) ** 2
        return np.array(boosted, np.uint8)

    @staticmethod
    def threshold(img):
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        value = (31, 31)
        blurred = cv2.GaussianBlur(grey, value, 0)
        retVal, thresh = cv2.threshold(blurred, 0, 255,
                                        cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        return thresh

    def setContours(self, img):
        self.contours, hierarchy = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Currently just finds the largest contour, which seems to work to some degree
    # Should be able to replace this with a "matching" algorithm instead, from here:
    # http://docs.opencv.org/trunk/doc/py_tutorials/py_imgproc/py_contours/py_contours_more_functions/py_contours_more_functions.html
    def findHandContour(self):
        maxArea, index = 0, 0
        for i in xrange(len(self.contours)):
            area = cv2.contourArea(self.contours[i])
            if area > maxArea:
                maxArea = area
                index = i
        self.handContour = self.contours[index]
        # self.hullHandContour = cv2.convexHull(self.handContour)
        self.hullHandContour = cv2.convexHull(self.handContour, returnPoints = False)
        self.defects = cv2.convexityDefects(self.handContour, self.hullHandContour)
        self.handMoments = cv2.moments(self.handContour)
        self.handXCenterMoment = int(self.handMoments["m10"]/self.handMoments["m00"])
        self.handYCenterMoment = int(self.handMoments["m01"]/self.handMoments["m00"])
        self.handCenterPositions += [(self.handXCenterMoment, self.handYCenterMoment)]
        if len(self.handCenterPositions) > 10:
            self.canDoGestures = True
        else: self.canDoGestures = False

    def analyzeHandCenter(self):
        # makes sure that there is actually sufficient data to trace over
        if len(self.handCenterPositions) > 10:
            self.recentPositions = sorted(self.handCenterPositions[-30:])
            self.x = [pos[0] for pos in self.recentPositions]
            self.y = [pos[1] for pos in self.recentPositions]
            self.poly = np.polyfit(self.x, self.y, 1)
            # print self.poly
        else:
            self.recentPositions = []

    def drawCenter(self):
        cv2.circle(self.drawingCanvas, (self.handXCenterMoment, self.handYCenterMoment), 10, (255, 255, 255), -2)
        if len(self.recentPositions) != 0:
            for i in xrange(len(self.recentPositions)):
                cv2.circle(self.drawingCanvas, self.recentPositions[i], 5, (255, 25*i, 25*i), -1)

    def draw(self):
        self.drawingCanvas = np.zeros(self.original.shape, np.uint8)
        self.drawHandContour(True)
        self.drawHullContour(True)
        self.drawDefects(True)
        self.drawCenter()
        cv2.circle(self.drawingCanvas, (0, 0), 30, (255, 255, 255), -1)
        cv2.circle(self.drawingCanvas, (500, 0), 30, (0, 255, 255), -1)
        cv2.imshow('HandContour', self.drawingCanvas)


    def setHandDimensions(self):
        rect = cv2.minAreaRect(self.handContour)

    def determineIfGesture(self):
        self.prevRecordState = self.record
        self.detemineStationary()
        if self.record:
            self.gesturePoints += [self.handCenterPositions[-1]]
        elif self.prevRecordState == True and not self.record:
            minGesturePoints = 5 # Should last a few frames at least
            if len(self.gesturePoints) > 5:
                # print "Gesture:", self.gesturePoints
                self.classifyGesture()
            self.gesturePoints = []

    def classifyGesture(self):
        minError = 2*31 - 1 # a large value
        minErrorIndex = -1
        for i in xrange(len(self.gestureTemplates)):
            error = self.gestureTemplates[i].compareGesture(self.gesturePoints) 
            print self.gestureTemplates[i].name, "Error:", error
            if error < minError:
                minError = error
                minErrorIndex = i
        print self.gestureTemplates[minErrorIndex].name

    def detemineStationary(self):
        # Figure out of the past few points have been at roughly the same position
        # If they have and there is suddenly movement, trigger the start of a gesture search
        searchLength = 3 # 3 frames should be enough
        val = -1 * (searchLength + 1)
        if self.canDoGestures:
            xPoints = [pt[0] for pt in self.handCenterPositions[val:-1]]
            yPoints = [pt[1] for pt in self.handCenterPositions[val:-1]]
            xAvg = np.average(xPoints)
            yAvg = np.average(yPoints)
            factor = 0.04
            for x, y in self.handCenterPositions[-(searchLength + 1):-1]:
                # if any point is further further from the average:
                if (x - xAvg) ** 2 + (y - yAvg) ** 2 > factor * min(self.cameraWidth, self.cameraHeight):
                    # If previous not moving, start recording
                    if self.stationary:
                        self.record = True
                        # print "Starting Gesture!"
                    self.stationary = False
                    self.stationaryTimeStart = time.time()
                    return
            # Not previously stationary but stationary now
            if not self.stationary:
                self.record = False
                # print "Ending Gesture!"
            self.stationary = True
            # print "Stationary!"

    def printValues(self):
        print "Hand Contour:"
        print self.handContour
        print
        print "Hull Point Indices:"
        print self.hullHandContour
        print 
        print "Defects:"
        print self.defects

    def process(self):
        while (self.cap.isOpened()):
            retVal, self.original = self.cap.read()
            self.original = cv2.flip(self.original, 1)
            self.boostContrast = HandProcessor.boostContrast(self.original)
            self.thresholded = HandProcessor.threshold(self.boostContrast)
            self.setContours(self.thresholded.copy())
            self.findHandContour()
            self.setHandDimensions()
            self.analyzeHandCenter()
            self.determineIfGesture()
            # self.printValues()
            # break
            self.draw()
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.close()

    def getPoint(self, index):
        if index < len(self.handContour):
            return (self.handContour[index][0][0], self.handContour[index][0][1])
        return None

    def drawHandContour(self, bubbles = False):
        cv2.drawContours(self.drawingCanvas, [self.handContour], 0, (0, 255, 0), 1)
        if bubbles:
            self.drawBubbles(self.handContour, (255, 255, 0))

    def drawHullContour(self, bubbles = False):
        hullPoints = []
        for i in self.hullHandContour:
            hullPoints.append(self.handContour[i[0]])
        hullPoints = np.array(hullPoints, dtype = np.int32)
        cv2.drawContours(self.drawingCanvas, [hullPoints], 0, (0, 0, 255), 2)
        if bubbles:
            self.drawBubbles(hullPoints, (255, 255, 255))

    def drawDefects(self, bubbles = False):
        defectPoints = []
        minDistance = 1000
        for i in self.defects:
            if i[0][3] > minDistance:
                defectPoints.append(self.handContour[i[0][2]])
        defectPoints = np.array(defectPoints, dtype = np.int32)
        if bubbles:
            self.drawBubbles(defectPoints, (0, 0, 255), width = 4)

    def drawBubbles(self, pointsList, color = (255, 255, 255), width = 2):
        for i in xrange(len(pointsList)):
            for j in xrange(len(pointsList[i])):
                cv2.circle(self.drawingCanvas, (pointsList[i][j][0], pointsList[i][j][1]), width, color)

HandProcessor().process()

class HandProcessorSingleImage(HandProcessor):
    def __init__(self):
        self.original = cv2.imread('oneHand.jpg')

    def process(self):
        self.boostContrast = HandProcessor.boostContrast(self.original)
        self.thresholded = HandProcessor.threshold(self.boostContrast)
        self.setContours(self.thresholded.copy())
        self.findHandContour()
        self.draw()
        if cv2.waitKey(0) & 0xFF == ord('q'):
            self.close()

    def close(self):
        cv2.destroyAllWindows()

    def draw(self):
        self.drawingCanvas = np.zeros(self.original.shape, np.uint8)
        self.drawHandContour(True)
        self.drawHullContour(True)
        self.drawDefects(True)
        cv2.imshow('HandContour', self.drawingCanvas)

# HandProcessorSingleImage().process()

# lineTemplate = GestureTemplate([(x, 0) for x in xrange(21)])
# print GestureTemplate.curveDistance([(0, 0), (100, 0), (200, 0)])
# print lineTemplate.compareGesture([(0, 0), (100, 0), (200, 0)])