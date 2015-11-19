import hibike_message as hm
import csv
import binascii
ZeroTime = -1.0

class Device():
    # [{param: (value, timestamp)}, delay, timestamp]
    #timestamp is the last time any field was modified in this device!
    # NOT TOUCHED BY USER?!
    # user
    def __init__(self, uid, deviceParams, context):
        # params - internal dictionary {paramIndex: (value, timestamp)}
        self.uid = uid
        dID = hm.getDeviceType(uid)
        self.deviceType = context.deviceTypes[dID]
        self.params = [(0, ZeroTime) for _ in self.deviceType.params]
        self._context = context
        self.delay = 0
        self.timestamp = ZeroTime

    def __contains__(self, item):
        return item in self.deviceType

    def __str__(self):
        deviceStr  = "Device %d: %s\n" % (self.uid
            , self.deviceType.deviceName)
        deviceStr += "    subcription: %dms @ %f\n" % (self.delay
            , self.timestamp)
        for i in range(len(self.params)):
            value = self.params[i][0]
            if type(value) is str:
                value = binascii.hexlify(value)
            else:
                value = str(value)
            deviceStr += "    %s: %s @ %f\n" % (self.deviceType.params[i]
                , value, self.params[i][1])
        return deviceStr

    # user exposed methods
    def getData(self, param):
        return self._getParam(param)
    def writeValue(self, param, value):
        self._context.writeValue(self.uid, param, value)
    def readValue(self, param, value):
        self._context.writeValue(self.uid, param, value)
    def subToDevice(self, delay):
        self._context.subToDevice(self.uid, delay)


    # not user exposed
    def _getParam(self, param):
        if type(param) is str:
            assert param in self.deviceType.paramIDs, "The parameter {0} does not exist for your specified device.".format(param)
            param = self.deviceType.paramIDs[param]
        assert param < len(self.params), "The parameter {0} does not exist for your specified device.".format(param)
        return self.params[param]

    def _getTimestamp(self, param):
        if type(param) is str:
            assert param in self.deviceType.paramIDs, "The parameter {0} does not exist for your specified device.".format(param)
            param = self.deviceType.paramIDs[param]
        assert param < len(self.params), "The parameter {0} does not exist for your specified device.".format(param)
        return self.params[param][1]

    def _setParam(self, param, value, time):
        if type(param) is str:
            assert param in self.deviceType.paramIDs, "The parameter {0} does not exist for your specified device.".format(param)
            param = self.deviceType.paramIDs[param]
        assert param < len(self.params), "The parameter {0} does not exist for your specified device.".format(param)
        self.params[param] = (value, time)

    def _updateSub(self, delay, time):
        self.delay = delay
        self.timestamp = time

# devicetype object. constructor takes in a row from the csv
class DeviceType():

    def __init__(self, csv_row):
        self.deviceID   = int(csv_row[0], 16)
        self.deviceName = csv_row[1]
        self.params = [param for param in csv_row[2:] if param != '']
        self.paramIDs   = {self.params[index]: index for index in range(len(self.params))}

    def __contains__(self, item):
        return item < len(self.params) or item in self.paramIDs

    def __str__(self):
        deviceType = "DeviceType %d: %s\n" % (self.deviceID, self.deviceName)
        deviceType += "\n".join(["    %s" % param for param in self.params])
        return deviceType

class DeviceContext():
    def __init__(self, configFile='hibikeDevices.csv'):
        # devices = {uid: Device() }
        self.deviceTypes = dict()
        self.devices = dict()
        self.deviceParams = dict()
        self.version = None
        self.hibike = None
        self._readConfig(configFile)

        # just for testing
        self.log = ([], [], [])

   #for each device in the list of UIDs, list out its paramters by name
    def getParams(self, uids):
        return [self.devices(uid).deviceType.params for uid in uids]

    def getDeviceName(self, deviceType):
        return hm.deviceTypes[deviceType]

    def _readConfig(self, filename):
        """
        Read the configuration information given in 'filename'
        Handle all IO Exceptions
        Fill out self.deviceParams and self.version

        Config file format:
        deviceID1, deviceName1, param1, param2, ...
        deviceID2, deviceName2, param1, param2, ...

        self.deviceParams format:
        self.deviceParams = {deviceID : (param1, param2, ...)}

        self.version format:
        self.version = <string repr of version info>
        """
        try:
            csv_file = open(filename, 'r')
            reader = csv.reader(csv_file, delimiter = ',', quotechar = '"', quoting = csv.QUOTE_MINIMAL)
            list_of_rows = [row for row in reader]
            list_of_rows.pop(0)
            self.deviceTypes = {int(lst[0], 16): DeviceType(lst) for lst in list_of_rows}
            self.deviceParams = {int(lst[0], 16): [elem for elem in lst[2:] if elem != ''] for lst in list_of_rows}
        except IOError:
            return "The file does not exist."
        finally:
            csv_file.close()

    def _addDeviceToContext(self, uid):
        """
        Add given device to self.devices, adding params specified
        by self.deviceParams based on the UID
        Handle invalid UIDs
        """
        #check for valid UID in the HibikeMessage class!!
        self.devices[uid] = Device(uid, self.deviceParams, self)

    def getData(self, uid, param):
        """
        Gets device that corresponds to UID
        Gets deviceType
        Gets paramID corresponding to param for that type
        Queries Device w/ that paramID
        Returns that parameter
        """
        if uid in self.devices:
            if param in self.deviceTypes[hm.getDeviceType(uid)].params:
                index = self.deviceTypes[hm.getDeviceType(uid)].params.index(param)
                return self.devices[uid].params[index]
            else:
                return "The parameter {0} does not exist for your specified device.".format(param)
        else:
            return "You have not specified a valid device. Check your UID."

    def _updateParam(self, uid, paramID, value, timestamp): # Hibike calling this?
        """
        Get Device
        If timestamp given > timestamp original, replace old tuple with new value & timestamp
        """
        if self.devices[uid]._getTimestamp(paramID) < timestamp:
            self.devices[uid]._setParam(paramID, value, timestamp)

    def _updateSubscription(self, uid, delay, timestamp):
        """
        Ack packet
        Update the delay and timestamp for given device
        """
        self.devices[uid]._updateSub(delay, timestamp)

    def subToDevices(self, deviceTuples):
        for devTup in deviceTuples:
            self.subToDevice(uid, delay)

    def subToDevice(self, uid, delay):
        assert self.hibike is not None, "DeviceContext needs a pointer to Hibike!"
        assert uid in self.devices, "Invalid UID: {}".format(uid)
        assert 0 <= delay <= 65535, "Invalid delay: {}".format(delay)
        self.hibike.subRequest(uid, delay)

    def writeValue(self, uid, param, value):
        assert self.hibike is not None, "DeviceContext needs a pointer to Hibike!"
        assert uid in self.devices, "Invalid UID: {}".format(uid)
        assert param in self.deviceParams[hm.getDeviceType(uid)], "Invalid param for {}".format(hm.getDeviceType(uid))
        
        self.hibike.deviceUpdate(uid, param, value)
    
    def readValue(self, uid, param):
        assert self.hibike is not None, "DeviceContext needs a pointer to Hibike!"
        assert uid in self.devices, "Invalid UID: {}".format(uid)
        assert param in self.deviceParams[hm.getDeviceType(uid)], "Invalid param for {}".format(hm.getDeviceType(uid))
        
        paramID = self.deviceTypes[hm.getDeviceType(uid)].params.index(param)
        self.hibike.deviceUpdate(uid, paramID, value)

    def getDelay(self, uid):
        if uid in self.devices:
            return self.devices[uid].delay
        else:
            return "You have not specified a valid device. Check your UID."
