import cv2
import numpy as np
import time
import math
import sys

class Gesture(object):
    __GestureMaxDim = 1024.0 # Nice round number

    def __init__(self, points, name = ""):
        self.points = np.array(points, dtype = np.float)
        self.points = Gesture.normalizePoints(self.points)
        scaleFactor = Gesture.__GestureMaxDim / Gesture.maxDim(self.points)["maxDim"]
        self.points *= scaleFactor
        self.distance = Gesture.curveLength(self.points)
        self.distance, self.distanceIndices = Gesture.curveLengthWithCumulativeDistanceIndices(self.points)
        self.name = name
        print self.name
        print self.distanceIndices

    @staticmethod
    def curveLength(points):
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
        gesturePoints = Gesture.normalizePoints(gesturePoints)
        # print "Normalized Gesture Points:", gesturePoints
        gestureDistance = Gesture.curveLength(gesturePoints)
        scaleFactor = self.distance / gestureDistance
        gesturePoints *= scaleFactor
        # print "Template:", self.points
        # print "Template Distance:", self.distance
        # print "Gesture Distance:", gestureDistance
        # print "Scale Factor:", scaleFactor
        # print "Adjusted Gesture Points:", gesturePoints
        # Both the template and the gesture will have (0, 0) for their start point
        # so that can be safely ignored
        # Directly map the indices of the gesture to the template
        totalError = 0
        for i in xrange(1, len(gesturePoints)):
            selfIndex = int(i * (len(self.points) - 1) / float((len(gesturePoints) -1)))
            # print i, self.points[selfIndex], gesturePoints[i]
            totalError += Gesture.error(self.points[selfIndex], gesturePoints[i])
        # print totalError
        # print totalError/gestureDistance
        return totalError/gestureDistance

    @staticmethod
    def maxDim(points):
        xMin, xMax, yMin, yMax = sys.maxsize, -sys.maxsize, sys.maxsize, -sys.maxsize
        for x, y in points:
            if x < xMin: xMin = x
            if x > xMax: xMax = x
            if y < yMin: yMin = y
            if y > yMin: yMax = y
        return {"xMin":xMin, "xMax":xMax, "yMin":yMin, "yMax":yMax,
                "maxDim": max(yMax-yMin, xMax-xMin)}

    def compareGestureMaxDim(self, gesturePoints):
        # Rip off the last couple points from gesture due to how we're determining gestures
        # gesturePoints = gesturePoints[:-2]
        gesturePoints = np.array(gesturePoints, dtype = float)
        # Make them both start at the same place
        gesturePoints = Gesture.normalizePoints(gesturePoints)
        # print "Normalized:", gesturePoints
        # Scale based on the max dimensions instead of distance
        # print "TemplateDim:", Gesture.maxDim(self.points)
        # print "GestureDim:", Gesture.maxDim(gesturePoints)
        scaleFactor = Gesture.maxDim(self.points)["maxDim"] / Gesture.maxDim(gesturePoints)["maxDim"]
        # print "Scale Factor:", scaleFactor
        gesturePoints *= scaleFactor
        # print "Scaled:", gesturePoints
        # Both the template and the gesture will have (0, 0) for their start point
        # so that can be safely ignored
        # Directly map the indices of the gesture to the template
        totalError = 0
        for i in xrange(1, len(gesturePoints)):
            selfIndex = int(i * (len(self.points) - 1) / float((len(gesturePoints) -1)))
            # print i, self.points[selfIndex], gesturePoints[i]
            totalError += Gesture.error(self.points[selfIndex], gesturePoints[i])
        # print totalError
        # print totalError/gestureDistance
        # print "Total Error:", totalError
        return totalError/scaleFactor

    @staticmethod
    # Takes points, returns an array of the same length with indices matching 
    # cumulative distance, to take linearization indices from.
    def curveLengthWithCumulativeDistanceIndices(points):
        indices = np.empty(len(points))
        cumulativeDistance = 0
        indices[0] = 0
        for i in xrange(1, len(points)):
            cumulativeDistance += Gesture.distance(points[i], points[i-1])
            indices[i] = cumulativeDistance
        return cumulativeDistance, indices

    @staticmethod
    def distance(point1, point2):
        return ((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2) ** 0.5

    @staticmethod
    def compareGestures(template, humanGesture):
        def findIndices(templateDistance):
            if (templateDistance > template.distanceIndices[-1] or
                templateDistance < template.distanceIndices[0]):
                return False
            start = 0
            end = len(template.distanceIndices)
            while True:
                mid = (start + end) / 2
                if template.distanceIndices[mid] == templateDistance:
                    return max(mid - 1, 0), min(mid + 1, len(template.distanceIndices)-1)
                elif start == end:
                    if templateDistance.distanceIndices[start] < templateDistance:
                        return start, min(start + 1, len(template.distanceIndices)-1)
                    else:
                        return max(start - 1, 0), start
                elif abs(start - end) == 1:
                    return (min(start, end), max(start, end))
                elif template.distanceIndices[mid] < templateDistance:
                    start = mid
                else:
                    end = mid

        def linearizeTemplate(templateDistance):
            minIndex, maxIndex = findIndices(templateDistance)
            distanceDiff = template.distanceIndices[maxIndex] - template.distanceIndices[minIndex]
            templateDistance -= template.distanceIndices[minIndex]
            scale = templateDistance / distanceDiff
            change = template.points[maxIndex] - template.points[minIndex]
            change *= scale
            return template.points[minIndex] + change

        # Can probably do something with a normal distribution and whatever
        totalDistance = 0
        totalError = 0
        distances = []
        for i in xrange(len(humanGesture.distanceIndices)):
            toFind = template.distance * humanGesture.distanceIndices[i] / humanGesture.distance
            comparePoint = linearizeTemplate(toFind)
            distance = Gesture.distance(comparePoint, humanGesture.points[i])
            totalDistance += distance
            distances += [distance]
            totalError += distance ** 2 # come up with a better error function?
        minDistance = min(distances)
        maxDistance = max(distances)
        distanceRange = minDistance - maxDistance
        return {"distanceList": distances, "minDistance": minDistance,
                "maxDistance": maxDistance, "totalDistance": totalDistance,
                "totalError", totalError}
        # Gesture distance determines number of partitions of the template curve
        # Subsequent distances form indices

    def comparePoints(self, distanceIndices):
        # Using the distance index of the gesture point, scale it up/down to 
        # match the max distance of the template curve. Then figure out which
        # of the values in the template distance indices hold the closest values
        # to the given index. Get the actual value of those two points, linearize
        # between them, and then figure out how far to tend toward one point
        # using the value of the template distance.
        pass


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
        self.initGestures()
        
    def initGestures(self):
        self.Gestures = []
        hLineLR = Gesture([(-x, 0) for x in xrange(17)],
            name="Horizontal Line Right to Left")
        self.Gestures.append(hLineLR)
        hLineRL = Gesture([(x, 0) for x in xrange(17)],
            name="Horizontal Line Left to Right")
        self.Gestures.append(hLineRL)
        # Y is reversed, remember?
        # let's try something more complicated, like a circle:
        circlePoints = [(10*math.cos(t), 10*math.sin(t)) for t in np.linspace(0, 2*math.pi, num=15)]
        ccwCircle = Gesture(circlePoints, name="CW Circle")
        self.Gestures.append(ccwCircle)
        circlePoints = [(10*math.cos(t), -10*math.sin(t)) for t in np.linspace(0, 2*math.pi, num=15)]
        cwCircle = Gesture(circlePoints, name="CCW Circle")
        self.Gestures.append(cwCircle)
        for i in self.Gestures:
            print i.points

        # for i in self.Gestures:
        #     print i.name
        #     print i.distance
        #     print np.array(i.points)


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
        else:
            self.recentPositions = []

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
        minError = 2**31 - 1 # a large value
        minErrorIndex = -1
        self.humanGesture = Gesture(self.gesturePoints)
        likelihoodScores = [0] * len(self.Gestures)
        assessments = [{}] * len(self.Gestures)
        for i in xrange(len(self.Gestures)):
            assessments[i] = Gestures.compareGestures(self.Gestures[i], self.humanGesture)
        def findMax(key):
            maxFound = 0
            maxIndex = 0
            for i in xrange(len(assessments)):
                if assessments[i][key] > maxFound:
                    maxIndex = i
            return i
        # add to scores based on the differences between values of gestures
        
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
            self.draw()
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.close()

    def getPoint(self, index):
        if index < len(self.handContour):
            return (self.handContour[index][0][0], self.handContour[index][0][1])
        return None

# Various Drawing Methods

    def drawCenter(self):
        cv2.circle(self.drawingCanvas, (self.handXCenterMoment, self.handYCenterMoment), 10, (255, 255, 255), -2)
        if len(self.recentPositions) != 0:
            for i in xrange(len(self.recentPositions)):
                cv2.circle(self.drawingCanvas, self.recentPositions[i], 5, (255, 25*i, 25*i), -1)

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

    def draw(self):
        self.drawingCanvas = np.zeros(self.original.shape, np.uint8)
        self.drawHandContour(True)
        self.drawHullContour(True)
        self.drawDefects(True)
        self.drawCenter()
        cv2.imshow('HandContour', self.drawingCanvas)
        cv2.imshow('Original', self.original)

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

# lineTemplate = Gesture([(x, 0) for x in xrange(301)])

# # print Gesture.curveLength([(0, 0), (100, 0), (200, 0)])
# # print lineTemplate.compareGestureMaxDim([(x, 0) for x in xrange(0, 300, 20)])
# circlePoints = [(10*math.cos(t), 10*math.sin(t)) for t in np.linspace(0, 2*math.pi, num=301)]
# ccwCircleTemplate = Gesture(circlePoints, name="CW Circle")

# parabolaPoints = [(t, 2**t) for t in np.linspace(0, 20, num = 20)]

# print lineTemplate.compareGestures(np.array(parabolaPoints))


# print lineTemplate.compareGestures(np.array(circlePoints)*20)
# print ccwCircleTemplate.compareGestures(np.array(circlePoints)*20)