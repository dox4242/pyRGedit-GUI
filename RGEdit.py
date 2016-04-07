################################################
## USAGE INSTRUCTIONS:                        ##
## DO NOT ENTER YOUR SAVE DATA IN THIS WINDOW ##
## PRESS THE RUN BUTTON ABOVE                 ##
## ENTER COMMANDS IN THE WINDOW TO THE RIGHT  ##
################################################

import zlib, json, base64, struct, copy
from Tkinter import *

class _Hierarchy(object):
  conditions = {
    '>=': lambda x,y: x >= y,
    '>': lambda x,y: x > y,
    '<=': lambda x,y: x <= y,
    '<': lambda x,y: x < y,
    '==': lambda x,y: x == y,
    '!=': lambda x,y: x != y
  }

  def __init__(self, data= None):
    object.__init__(self)
    self.data = copy.deepcopy(data) if data != None else {}

  def __contains__(self, addr):
    elem = self.data
    for key in addr:
      if key not in elem:
        return False
      elem = elem[key]
    return True

  def __getitem__(self, addr):
    elem = self.data
    for key in addr:
      elem = elem[key]
    return elem

  def __setitem__(self, addr, value):
    elem = self.data
    for key in addr[:-1]:
      if key not in elem:
        elem[key] = {}
      elem = elem[key]
    elem[addr[-1]] = value

  def __delitem__(self, addr):
    elem = self.data
    for key in addr[:-1]:
      elem = elem[key]
    del elem[addr[-1]]

  def get(self, attr, default= None):
    if (attr in self):
      return self[attr]
    else:
      return default

  def cond(self, rule):
    return self.conditions[rule[1]](self[rule[0]], rule[2])

class _DataView(object):
  dtypes = {
    'Int8': ('b', 1),
    'Uint8': ('B', 1),
    'Bool': ('?', 1),
    'Int16': ('h', 2),
    'Uint16': ('H', 2),
    'Int32': ('i', 4),
    'Int': ('i', 4),
    'Uint32': ('I', 4),
    'Uint': ('I', 4),
    'Int64': ('q', 8),
    'Uint64': ('Q', 8),
    'Float': ('f', 4),
    'Float32': ('f', 4),
    'Double': ('d', 8),
    'Float64': ('d', 8)
  }

  def __init__(self, data= 0):
    object.__init__(self)
    self.buffer = bytearray(data)
    self.position = len(self.buffer)

  def __len__(self):
    return len(self.buffer)

  def pad(self, size):
    if (len(self) - self.position < size):
      self.buffer += bytearray(len(self) - self.position + size)

  def formatStr(self, format):
    formatStr = ''.join(['>'] + [self.dtypes[x][0] for x in format])
    size = sum([self.dtypes[x][1] for x in format])
    return formatStr, size

  def resolveInt(self, query, writing= False):
    if writing:
      if (query[0] == '_len'):
        return len(self.save[query[1:]])
    try:
      val = int(self.save[query])
    except TypeError:
      val = int(query)
    return val

  def readVal(self, dtype):
    format, size = self.formatStr((dtype,))
    val = struct.unpack_from(format, self.buffer, self.position)[0]
    self.position += size
    return val
      
  def readArray(self, items, length):
    arr = []
    for i in xrange(length):
      arr.append(self.read(items))
    return arr
      
  def readMuxedArray(self, items, length):
    muxCount = len(items)
    arrs = [[] for x in xrange(muxCount)]
    for i in xrange(length):
      for j in xrange(muxCount):
        arrs[j].append(self.read(items[j]))
    return arrs

  def readObject(self, members):
    obj = {}
    for member in members:
      val = self.read(member)
      if 'key' in member: obj[member['key']] = val
    return obj

  def read(self, elem):
    format = elem['format']
    if (format in self.dtypes):
      return self.readVal(format)
    elif (format == 'Empty'):
      self.position += elem['width']
      return None
    elif (format == 'Array'):
      length = self.resolveInt(elem['length'])
      return self.readArray(elem['items'], length)
    elif (format == 'MuxedArray'):
      length = self.resolveInt(elem['length'])
      return self.readMuxedArray(elem['items'], length)
    elif (format == 'Object'):
      return self.readObject(elem['members'])
    else:
      raise ValueError, 'unknown format: %s' % format

  def parseStruct(self, format, keepStash= False):
    self.save = _Hierarchy()
    self.position = 0
    for elem in format:
      if ('cond' in elem and not self.save.cond(elem['cond'])):
        continue
      key = elem.get('save', None)
      val = self.read(elem)
      if (key):
        if (elem['format'] == 'MuxedArray'):
          for i in xrange(len(key)):
            if (len(key) > i and key[i]):
              self.save[key[i]] = val[i]
        else:
          self.save[key] = val
    save = self.save
    del self.save
    if (not keepStash):
      del save[['_index']]
      del save[['_len']]
    return save.data

  def writeVal(self, dtype, val):
    format, size = self.formatStr((dtype,))
    self.pad(size)
    struct.pack_into(format, self.buffer, self.position, val)
    self.position += size

  def writeArray(self, items, length, arr):
    for i in xrange(length):
      self.write(items, arr[i])

  def writeMuxedArray(self, items, length, arrs):
    muxCount = len(items)
    for i in xrange(length):
      for j in xrange(muxCount):
        self.write(items[j], arrs[j][i])

  def writeObject(self, members, obj):
    for member in members:
      self.write(member, obj[member['key']] if 'key' in member else None)

  def write(self, elem, val= None):
    format = elem['format']
    if (format in self.dtypes):
      val = val if val else 0
      self.writeVal(format, val)
    elif (format == 'Empty'):
      self.pad(elem['width'])
      self.position += elem['width']
    elif (format == 'Array'):
      val = val if val else []
      length = self.resolveInt(elem['length'], writing= True)
      if (len(val) < length):
        val += [None] * (length - len(val))
      self.writeArray(elem['items'], length, val)
    elif (format == 'MuxedArray'):
      muxCount = len(elem['items'])
      val = val if val else [[] for i in xrange(muxCount)]
      length = self.resolveInt(elem['length'], writing= True)
      for i in xrange(muxCount):
        if (len(val[i]) < length):
          val[i] += [None] * (length - len(val[i]))
      self.writeMuxedArray(elem['items'], length, val)
    elif (format == 'Object'):
      val = val if val else {}
      for member in elem['members']:
        if (member['key'] not in val):
          val[member['key']] = None
      self.writeObject(elem['members'], val)
    else:
      raise ValueError, 'unknown format: %s' % format

  def writeIndex(self, indexAddr, indexElem):
    currPos = self.position
    self.position = indexAddr
    self.write(indexElem, currPos)
    self.position = currPos

  def checkIndex(self, elem):
    key = elem['save']
    if (key[0] == '_index'):
      self.index[tuple(key[1:])] = (self.position, elem)
    keys = []
    if (elem['format'] == 'MuxedArray'):
      for key in elem['save']:
        keys.append(tuple(key))
    else:
      keys.append(tuple(key))
    for key in keys:
      if (key in self.index):
        indexAddr, indexElem = self.index.pop(tuple(key))
        self.writeIndex(indexAddr, indexElem)

  def compileStruct(self, format, save):
    self.save = _Hierarchy(save)
    self.index = {}
    self.position = 0
    for elem in format:
      if ('cond' in elem and not self.save.cond(elem['cond'])):
        continue
      key = elem.get('save', None)
      if (key):
        self.checkIndex(elem)
        if (elem['format'] == 'MuxedArray'):
          val = []
          for i in elem['save']:
            val.append(self.save.get(i))
          self.write(elem, val)
        else:
          if (elem['save'][0] == '_len'):
            val = self.resolveInt(key, writing= True)
          else:
            val = self.save.get(key)
          self.write(elem, val)
      else:
        self.write(elem)
    del self.save
    return self.buffer[:self.position]

def LRC_consts():
  c = []
  for i in xrange(256):
    v = i
    for j in xrange(7, -1, -1):
      if (v & 1):
        v = 3988292384 ^ v >> 1
      else:
        v = v >> 1
    c.append(v)
  return c

def LRC(data, length= None, consts=LRC_consts()):
  data = bytearray(data)
  v = 4294967295
  length = length if length != None else len(data)
  for i in xrange(length):
    addr = (v ^ data[i]) & 255
    v = consts[addr] ^ v >> 8
  return 4294967295 - v

_decodeJson = lambda x: (json.loads(zlib.decompress(base64.b64decode(x[2:-2]))), True)
_encodeJson = lambda x: '$s%s$e' % base64.b64encode(zlib.compress(json.dumps(x)))

def _encodeSol(save):
  data = json.dumps(save)
  return '$s0' + base64.b64encode(data) + '$e' + string(lrc(data))

def _decodeSol(data):
  data = data.split('$e')
  lrc = int(data[1])
  save = base64.b64decode(data[0][3:])
  return json.loads(save), (lrc == LRC(save))

def vigenere(data, key, rejoin= True):
  data = bytearray(data)
  key = bytearray(key)
  for i in xrange(len(data)):
    data[i] = data[i] ^ key[i % len(key)]
  return bytes(data) if (rejoin) else data

_structFormat = [
  {'format': 'Uint16', 'save': ['saveVersion']},
  {'format': 'Empty',  'width': 10},
  {'format': 'Uint32', 'save': ['eggRngState'], 'cond': [['saveVersion'], '>=', 15]},
  {'format': 'Empty',  'width': 4, 'cond': [['saveVersion'], '<', 15]},
  {'format': 'Uint16', 'save': ['eggStackSize'], 'cond': [['saveVersion'], '>=', 15]},
  {'format': 'Empty',  'width': 2, 'cond': [['saveVersion'], '<', 15]},
  {'format': 'Uint16', 'save': ['ctaFactionCasts'], 'cond': [['saveVersion'], '>=', 13]},
  {'format': 'Empty',  'width': 2, 'cond': [['saveVersion'], '<', 13]},
  {'format': 'Uint32', 'save': ['_index', 'alignment']},
  {'format': 'Uint32', 'save': ['_index', 'options']},
  {'format': 'Uint16', 'save': ['_len', 'build']},
  {'format': 'Array',  'save': ['build'], 'length': ['_len', 'build'], 'items':
    {'format': 'Object', 'members': [
      {'format': 'Uint32',  'key': '_id'},
      {'format': 'Uint32',  'key': 'q'},
      {'format': 'Float64', 'key': 't'},
      {'format': 'Float64', 'key': 'm'},
      {'format': 'Float64', 'key': 'r'},
      {'format': 'Float64', 'key': 'e'}
    ]}
  },
  {'format': 'Uint16', 'save': ['_len', 'upgrade']},
  {'format': 'Array',  'save': ['upgrade'], 'length': ['_len', 'upgrade'], 'items':
    {'format': 'Object', 'members': [
      {'format': 'Uint32', 'key': '_id'},
      {'format': 'Bool',   'key': 'u1'},
      {'format': 'Bool',   'key': 'u2', 'cond': [['saveVersion'], '>=', 1]},
      {'format': 'Uint32', 'key': 's'}
    ]}
  },
  {'format': 'Uint16', 'save': ['_len', 'trophy']},
  {'format': 'Array',  'save': ['trophy'], 'length': ['_len', 'trophy'], 'items':
    {'format': 'Object', 'members': [
      {'format': 'Uint32', 'key': '_id'}
    ]}
  },
  {'format': 'Uint32', 'save': ['artifactRngState'], 'cond': [['saveVersion'], '>=', 4]},
  {'format': 'Uint16', 'save': ['_len', 'spell']},
  {'format': 'Array',  'save': ['spell'], 'length': ['_len', 'spell'], 'items':
    {'format': 'Object', 'members': [
      {'format': 'Uint32',  'key': '_id'},
      {'format': 'Int32',   'key': 't'},
      {'format': 'Bool',    'key': 'a'},
      {'format': 'Int32',   'key': 'n'},
      {'format': 'Int32',   'key': 'n2'},
      {'format': 'Int32',   'key': 'n3', 'cond': [['saveVersion'], '>=', 5]},
      {'format': 'Float64', 'key': 'c'},
      {'format': 'Float64', 'key': 'r'},
      {'format': 'Float64', 'key': 'e'},
      {'format': 'Float64', 'key': 'active0', 'cond': [['saveVersion'], '>=', 14]},
      {'format': 'Float64', 'key': 'active1', 'cond': [['saveVersion'], '>=', 14]},
      {'format': 'Float64', 'key': 'active2', 'cond': [['saveVersion'], '>=', 14]},
      {'format': 'Uint32',  'key': 's'}
    ]}
  },
  {'format': 'Uint8',   'save': ['alignment']},
  {'format': 'Uint8',   'save': ['faction']},
  {'format': 'Uint8',   'save': ['activeFaction']},
  {'format': 'Float64', 'save': ['gems']},
  {'format': 'Uint16',  'save': ['rei']},
  {'format': 'Uint16',  'save': ['ascension']},
  {'format': 'Uint32',  'save': ['lastsave']},
  {'format': 'Float64', 'save': ['mana']},
  {'format': 'Float64', 'save': ['resource']},
  {'format': 'Float64', 'save': ['rubies'], 'cond': [['saveVersion'], '>=', 4]},
  {'format': 'Float64', 'save': ['excavations'], 'cond': [['saveVersion'], '>=', 4]},
  {'format': 'Uint16',  'save': ['_len', 'secondaryResources']},
  {'format': 'MuxedArray', 'length': ['_len', 'secondaryResources'],
    'items': [{'format': 'Float64'}, {'format': 'Uint32'}],
    'save': [['secondaryResources'], ['royalExchangeFaction']]
  },
  {'format': 'Uint16', 'save': ['_len', 'extraResources'], 'cond': [['saveVersion'], '>=', 7]},
  {'format': 'Array',  'save': ['extraResources'], 'length': ['_len', 'extraResources'],
    'cond': [['saveVersion'], '>=', 7],
    'items': {
      'format': 'Float64'
    }
  },
  {'format': 'Uint16', 'save': ['_len', 'stats']},
  {'format': 'MuxedArray', 'length': ['_len', 'stats'],
    'items': [{'format': 'Float64'}, {'format': 'Float64'}, {'format': 'Float64'}],
    'save': [['stats'], ['statsReset'], ['statsRei']]
  },
  {'format': 'Bool',    'save': ['cont']},
  {'format': 'Float64', 'save': ['contv']},
  {'format': 'Int8',    'save': ['strikeTier']},
  #{'format': 'Uint8',   'save': ['empoweredTier']},
  #{'format': 'Uint8',   'save': ['empoweredTier2'], 'cond': [['saveVersion'], '>=', 5]}, #new 1
  #{'format': 'Float64', 'save': ['empoweredBonus']},
  #{'format': 'Float64', 'save': ['empoweredBonus2'], 'cond': [['saveVersion'], '>=', 5]}, #new 9
  {'format': 'Int32',   'save': ['miracleTier'], 'cond': [['saveVersion'], '>=', 3]}, #new 13
  {'format': 'Int32',   'save': ['miracleTimer'], 'cond': [['saveVersion'], '>=', 3]}, #new 17
  {'format': 'Uint8',   'save': ['snowballScryUses'], 'cond': [['saveVersion'], '>=', 9]}, #new 18
  {'format': 'Uint16',  'save': ['snowballSize'], 'cond': [['saveVersion'], '>=', 9]}, #new 20
  {'format': 'Uint32',  'save': ['lastGiftDate'], 'cond': [['saveVersion'], '>=', 9]}, #new 24
  {'format': 'Int32',   'save': ['chargedTimer']},
  {'format': 'Int32',   'save': ['comboStrike']},
  {'format': 'Int32',   'save': ['comboStrikeCont']},
  {'format': 'Int32',   'save': ['goblinTimer']},
  {'format': 'Int32',   'save': ['somethingNew'], 'cond': [['saveVersion'], '>=', 11]},
  {'format': 'Uint32',  'save': ['msp']},
  {'format': 'Uint32',  'save': ['msp2']},
  {'format': 'Int32',   'save': ['cTimer']},
  {'format': 'Int32',   'save': ['kcTimer']},
  {'format': 'Int32',   'save': ['mTimer']},
  {'format': 'Float64', 'save': ['sTimer']},
  {'format': 'Float64', 'save': ['oTimer']},
  {'format': 'Float64', 'save': ['oTimer2']},
  {'format': 'Float64', 'save': ['oTimer3'], 'cond': [['saveVersion'], '>=', 13]},
  {'format': 'Uint8',   'save': ['season'], 'cond': [['saveVersion'], '>=', 2]},
  {'format': 'Uint8',   'save': ['bFaction']},
  {'format': 'Uint8',   'save': ['buyMode']},
  {'format': 'Uint8',   'save': ['excavBuyMode'], 'cond': [['saveVersion'], '>=', 10]},
  {'format': 'Uint32',  'save': ['gameVersion']},
  {'format': 'Uint8',   'save': ['gameVersionRevision']},
  {'format': 'Object',  'save': ['options'], 'members': [
    {'format': 'Uint8', 'key': 'not'},
    {'format': 'Uint8', 'key': 'tab'},
    {'format': 'Bool',  'key': 'skipCloud'},
    {'format': 'Bool',  'key': 'floatingText'},
    {'format': 'Bool',  'key': 'buildingGlow'},
    {'format': 'Bool',  'key': 'manaGlow'},
    {'format': 'Bool',  'key': 'treasureGlow'},
    {'format': 'Bool',  'key': 'assistant'},
    {'format': 'Bool',  'key': 'thousandsSep'},
    {'format': 'Bool',  'key': 'toast'},
    {'format': 'Bool',  'key': 'sortLocked'},
    {'format': 'Bool',  'key': 'sortUnlocked'},
    {'format': 'Bool',  'key': 'multiUpgrade'},
    {'format': 'Bool',  'key': 'conUpgrade'},
    {'format': 'Bool',  'key': 'conTrophy'},
    #{'format': 'Bool',  'key': 'disableKred', 'cond': [['saveVersion'], '<', 12]},
    {'format': 'Bool',  'key': 'disableGOTH', 'cond': [['saveVersion'], '>=', 12]},
    {'format': 'Bool',  'key': 'warnExcavation'},
    {'format': 'Bool',  'key': 'warnExchange'},  
    {'format': 'Bool',  'key': 'warnRuby', 'cond': [['saveVersion'], '>=', 6]},      
    {'format': 'Bool',  'key': 'hideUpgHeader'},
    {'format': 'Bool',  'key': 'blockClick'},
    {'format': 'Bool',  'key': 'spellTimer'},
    {'format': 'Bool',  'key': 'spellIcon'},
    {'format': 'Bool',  'key': 'buyButton'},
    {'format': 'Bool',  'key': 'hideUnlocked'},
    {'format': 'Bool',  'key': 'disableGOTK', 'cond': [['saveVersion'], '>=', 12]},
    {'format': 'Bool',  'key': 'disableGOTG', 'cond': [['saveVersion'], '>=', 12]},
    {'format': 'Bool',  'key': 'hideLockedResearches', 'cond': [['saveVersion'], '>=', 12]}
  ]}
]

def _encodeStruct(save):
  dataView = _DataView(20000)
  data = dataView.compileStruct(_structFormat, save)
  lrc = bytearray(4)
  struct.pack_into('>I', lrc, 0, LRC(data))
  data += lrc
  data = vigenere(data, 'therealmisalie', rejoin= True)
  data = zlib.compress(data)
  return '$00s%s$e' % base64.b64encode(data)

def _decodeStruct(data):
  data = base64.b64decode(data[4:-2])
  data = zlib.decompress(data)
  data = vigenere(data, 'therealmisalie', rejoin= False)
  lrc = struct.unpack('>I', data[-4:])
  dataView = _DataView(data[:-4])
  return dataView.parseStruct(_structFormat, keepStash= False), lrc[0] == LRC(data[:-4])

def detectVersion(data):
  if (data[:2] == '$s'):
    if (data[-2:] == '$e'):
      return 'json'
    else:
      parts = data.split('$e')
      if (len(parts) == 1):
        return None
      else:
        try:
          return 'sol' if (data[2] == '0' and int(parts[1]) > -1) else None
        except ValueError:
          return None
  elif (data[:4] == '$00s' and data[-2:] == '$e'):
    return 'struct'
  else:
    return None

encoders = {'json': _encodeJson, 'sol': _encodeSol, 'struct': _encodeStruct}
decoders = {'json': _decodeJson, 'sol': _decodeSol, 'struct': _decodeStruct}

def encode(save, version= 'struct', **opts):
  return encoders[version](save, **opts)

def decode(data):
  version = detectVersion(data)
  if (version):
    return (decoders[version])(data)
  return None, None
  
# edit assistant
LightningRod = [
  [
    [9, 9, 8, 8, 10, 8, 10, 8, 8, 9, 9],
    [
      [1348656067],
      [2066742637],
      [724761641, 841926079, 1083420683, 1183205704, 1524485329, 2089628487],
      [1139776337, 1481055962, 1744916442, 1776475419, 2117755044],
      [1832831073],
      [2874410, 226737943, 338405215, 527131743, 568017568, 868411368, 909297193, 1238186454, 1275498097, 1579466079, 1620351904, 1809078432, 1920745704, 2144609237],
      [314652574],
      [29728603, 371008228, 402567205, 666427685, 1007707310],
      [57855160, 622998318, 964277943, 1064062964, 1305557568, 1422722006],
      [80741010],
      [798827580]
    ]
  ],
  [
    [9, 8, 10, 10, 9, 9, 10, 10, 8, 9],
    [
      [1348656067],
      [195509834, 1004832900, 1036391877, 1069861681, 1095291073, 1336785677, 1346112525, 1411141306, 1436570698, 1640753659, 1678065302, 1777850323, 1876118678, 1917004503, 2001713856],
      [1092747531],
      [1369388690],
      [124895406, 257516277],
      [1889967370, 2022588241],
      [778094957],
      [1054736116],
      [145769791, 230479144, 271364969, 369633324, 469418345, 506729988, 710912949, 736342341, 801371122, 810697970, 1052192574, 1077621966, 1111091770, 1142650747, 1951973813],
      [798827580]
    ]
  ],
  [
    [10, 9, 9, 10, 9, 10, 9, 9, 10],
    [
      [1019766806],
      [1010581720, 1305226700, 1437847571, 1575724878],
      [293919951, 926266528, 967152353, 1494983868, 1532295511, 1913572083],
      [1832831073],
      [274387307, 1873096340],
      [314652574],
      [233911564, 615188136, 652499779, 1180331294, 1221217119, 1853563696],
      [571758769, 709636076, 842256947, 1136901927],
      [1127716841]
    ]
  ],
  [
    [10, 10, 9, 10, 10, 9, 10, 10],
    [
      [1019766806],
      [72980725, 247391352, 1182309596],
      [44627026, 167428665, 168324773, 207536167, 253034126, 297371462, 385654997, 929840710, 967152353, 1239561358, 1276873001, 1283002586, 1454098043, 1494983868, 1876260440, 2005307129],
      [1267687915, 1832831073],
      [314652574, 879795732],
      [142176518, 271223207, 652499779, 693385604, 864481061, 870610646, 907922289, 1180331294, 1217642937, 1761828650, 1850112185, 1894449521, 1939947480, 1979158874, 1980054982, 2102856621],
      [965174051, 1900092295, 2074502922],
      [1127716841]
    ]
  ],
  [
    [10, 10, 10, 10, 10, 10, 10],
    [
      [454623648, 711956985, 1019766806, 1140248967, 1572771254, 1705392125],
      [54592755, 72980725, 117318061, 1759850348, 1892471219],
      [260059819, 611446935, 1008432339, 1176590093, 1369388690, 1685238923],
      [404214639, 705114232, 1442369415, 1743269008],
      [462244724, 778094957, 970893554, 1139051308, 1536036712, 1887423828],
      [255012428, 387633299, 2030165586, 2074502922, 2092890892],
      [442091522, 574712393, 1007234680, 1127716841, 1435526662, 1692859999]
    ]
  ],
  [
    [12, 12, 12, 12, 12, 12],
    [
      [770473881, 1007628096, 2057921582],
      [821234634, 1504312373],
      [250490584],
      [1896993063],
      [643171274, 1326249013],
      [89562065, 1139855551, 1377009766]
    ]
  ],
  [
    [14, 13, 12, 13, 14],
    [
      [770473881],
      [419517449, 1327606757],
      [527131743, 1620351904],
      [819876890, 1727966198],
      [1377009766]
    ]
  ],
  [
    [15, 15, 15, 15],
    [
      [1408849714],
      [355243782, 1195615159],
      [951868488, 1792239865],
      [738633933]
    ]
  ],
  [
    [18, 17, 18],
    [
      [918066031, 1096955941],
      [129106684, 200160515, 264547473, 1882936174, 1947323132, 2018376963],
      [1050527706, 1229417616]
    ]
  ],
  [
    [28, 28],
    [
      [1202476373, 1699695831],
      [447787816, 945007274]
    ]
  ]
]

import cmd, random

def tabulate(body, header= None, sep= '-', dist= 4):
  widths = [len(str(x)) for x in header] if header else [0] * len(body[0])
  for row in body:
    widths = [max(widths[i], len(str(row[i]))) for i in range(len(widths))]
  widths = [widths[0]] + [x + dist for x in widths[1:]]
  format = ''.join(['%%%ds' % x for x in widths])
  rows = []
  if header:
    rows.append(format % tuple(header))
    rows.append('-' * len(rows[0]))
  for row in body:
    rows.append(format % tuple(row))
  return '\n'.join(rows)

class EditAssist(cmd.Cmd):
  trophies = {
    'good': (93, 'Perfectly Good'),
    'evil': (67, 'Diabolical Evil'),
    'neutral': (85, 'Lucky Neutral'),
    'equal': (68, 'Equality'),
    'beard': (63, 'Beard Carpet'),
    'thanks': (115, 'Thanksgiving'),
    'stone': (151, 'Rough Stone'),
    'device': (160, 'Ancient Device'),
    'scarab': (119, 'Scarab of Fortune')
  }
  def __init__(self):
    cmd.Cmd.__init__(self)

    self.intro = '\n'.join(['this assistant will help perform some common save editing tasks',
      'type \'help\' to see a list of commands, or type \'exit\' if you wish to edit manually'])

    self.prompt = '>> '

    self.save = None

    self.trophy_cmds = {
      'add': (self.trophy_add, '[id or short name]', 'adds a trophy to stored save'),
      'del': (self.trophy_del, '[id or short name]', 'removes a trophy from stored save'),
      'list': (self.trophy_list, '', 'lists trophies with short names'),
      'list2': (self.list2,'','')
    }

    self.lightning_cmds = {
      'none': (self.lightning_none, '', 'sets LS to hit nothing forever'),
      'random': (self.lightning_random, '', 'sets LS to a random state'),
      'streak': (self.lightning_streak, '[x] [y] (m)', 'sets LS to hit the xth target out of a y bunch; if the letter "m" is added at the end, Miracle seed will be changed instead'),
      'show': (self.lightning_show, '', 'displays current LS state'),
      'set': (self.lightning_set, '[0-2147483647]', 'sets state to specified value')
    }

  def getstate(self):
    return [x for x in self.save['spell'] if x['_id'] == 13][0]['s']

  def setstate(self, state, miracle=None):
    if miracle == 'm':
        [x for x in self.save['upgrade'] if x['_id'] == 143719][0]['s'] = state
    else:
        [x for x in self.save['spell'] if x['_id'] == 13][0]['s'] = state

  def lightning_none(self, x):
    if (self.checksave()): return
    self.setstate(2147483647)
    print('LS RNG state set to 2147483647, will hit nothing forever')
    print('warning: you WILL need to edit your save again to return LS to normal behavior')

  def lightning_random(self, x):
    if (self.checksave()): return
    newstate = random.randint(1, 2147483646)
    self.setstate(newstate)
    print('LS RNG state set to %d' % newstate)

  def lightning_show(self, x):
    if (self.checksave()): return
    print('current LS RNG state: %d' % self.getstate())

  def lightning_set(self, x):
    if (self.checksave()): return
    valid = True
    try:
      x = int(x)
    except ValueError:
      valid = False
    if (not valid or x < 0 or x > 2147483647):
      print ('invalid seed: %s' % (str(x)))
      return
    self.setstate(x)
    print('LS RNG state set to %d' % x)

  def lightning_streak(self, x):
    if (self.checksave()): return
    x = x.split()
    try:
      n, m = int(x[0]), int(x[1])
    except (ValueError, TypeError, IndexError):
      print('error: requires two numbers')
      return
    if (m > 11 or n > m or m < 2 or n < 1):
      print ('error: parameters out of range')
      return
    hitcount = LightningRod[11 - m][0][n - 1]
    newstate = random.choice(LightningRod[11 - m][1][n - 1])
    try:
        if x[2] in ['m', 'M']:
            self.setstate(newstate, 'm')
            msg = 'Miracle RNG state set to %d, will hit building %d of %d %d times' % (newstate, n, m, hitcount)
        else:
            self.setstate(newstate)
            msg = 'LS RNG state set to %d, will hit building %d of %d %d times' % (newstate, n, m, hitcount)
    except IndexError:
        self.setstate(newstate)
        msg = 'LS RNG state set to %d, will hit building %d of %d %d times' % (newstate, n, m, hitcount)
    print(msg)

  def checksave(self):
    if (not self.save):
      print('error: you need to decode a save first')
      return True

  def trophy_add(self, x):
    if (self.checksave()): return
    numid, name = self.resolvetrophy(x)
    if (not numid):
      print('error: unknown trophy short name or id: %s' % x)
      return
    i = self.trophyindex(numid)
    if (i > -1):
      print('error: you already have %s' % name)
      return
    self.save['trophy'].append({'_id':numid})
    print('trophy added: %s' % name)

  def trophy_del(self, x):
    if (self.checksave()): return
    numid, name = self.resolvetrophy(x)
    if (not numid):
      print('error: unknown trophy short name or id: %s' % x)
      return
    i = self.trophyindex(numid)
    if (i == -1):
      print('error: you do not have %s' % name)
      return
    del self.save['trophy'][i]
    print('trophy removed: %s' % name)

  def trophy_list(self, x):
    header = ('short name', 'id', 'trophy')
    body = [(trophy,) + self.trophies[trophy] for trophy in self.trophies]
    print(tabulate(body, header))

  def list2(self, x):
    for trophy in self.save['trophy']:
        print(trophy)

  def trophyindex(self, numid):
    for i in range(len(self.save['trophy'])):
      if (self.save['trophy'][i]['_id'] == numid):
        return i
    return -1

  def resolvetrophy(self, x):
    try:
      return int(x), 'Trophy %d' % int(x)
    except (ValueError, TypeError):
      if (x not in self.trophies):
        return None, None
      return self.trophies[x]

  def do_decode(self, x):
    'decode [export code] -- decodes save and stores save data in the assistant'
    #if (not x):
    #  x = pyperclip.paste()
    try:
      self.save, self.valid = decode(x)
    except:
      self.save, self.valid = None, False
    if (self.valid):
      print('save decoded successfully')
    else:
      print('invalid save')

  def do_encode(self, x):
    'encode -- encodes stored save and prints an export code'
    print(encode(self.save))

  def subcommands(self, name, x, subcmds):
    x = x.partition(' ')
    subcmd = x[0]
    if (not subcmd):
      print('%s requires a subcommand, type \'help %s\' for help' % (name, name))
      return
    x = x[2]
    if (subcmd in subcmds):
      subcmds[subcmd][0](x)
    else:
      print('unknown subcommand %s %s, type \'help %s\' for help' % (name, subcmd, name))

  def subcommandhelp(self, name, subcmds):
    body = [('%s %s' % (name, x),) + subcmds[x][1:] for x in subcmds]
    print(tabulate(body, ('command', 'options', 'description'), dist= 2))

  def help_howto(self):
    print('\n'.join(['The general process of editing a save is:',
      '  decode [save data]',
      '  <various edit commands>',
      '  encode',
      'then copy the resulting export code',
      'paste your exported code after decode with a space between them',
      'but do not put brackets or quotes around the code, e.g.',
      '  decode $00s..$e',
      'edit commands available:',
      '  trophy -- can add and remove trophies']))

  def help_trophy(self):
    self.subcommandhelp('trophy', self.trophy_cmds)

  def do_trophy(self, x):
    self.subcommands('trophy', x, self.trophy_cmds)

  def help_lightning(self):
    self.subcommandhelp('lightning', self.lightning_cmds)

  def do_lightning(self, x):
    self.subcommands('lightning', x, self.lightning_cmds)

  def do_exit(self, x):
    'closes edit assistant'
    print('if you wish to reopen the assistant, type \'ea.cmdloop()\'')
    return True

  def resolveint(self, x):
    try:
      return int(x)
    except (ValueError, TypeError):
      print('error: invalid number')
      return None

  def getstat(self, statid, level):
    val = self.save['stats'][statid]
    if (level >= 1): val += self.save['statsReset'][statid]
    if (level >= 2): val += self.save['statsRei'][statid]
    return val

  def quantStatPrint(self, quantity, stat):
    if (quantity):
      qval = self.save
      for i in quantity[0]:
        qval = qval[i]
      print('%s: %d' % (quantity[1], qval))
    if (stat):
      sval = self.getstat(stat[0], stat[2])
      print('%s: %d' % (stat[1], sval))

  def quantStatAdd(self, x, quantity, stat, added):
    if (quantity):
      node = self.save
      for i in quantity[0][:-1]:
        node = node[i]
      node[quantity[0][-1]] += x
    if (stat):
      self.save[('stats', 'statsReset', 'statsRei')[stat[3]]][stat[0]] += x
    print('%d %s' % (x, added))

  def quantStatCommand(self, x, quantity, stat, added):
    if (not x.strip()):
      self.quantStatPrint(quantity, stat)
      return
    x = self.resolveint(x)
    if (x is None): return
    self.quantStatAdd(x, quantity, stat, added)
    
  def do_snowball(self, x):
    '''snowball [snowballs to add] -- adds snowballs
    snowball -- prints current and found snowballs'''
    self.quantStatCommand(x, (('extraResources', 0), 'current snowballs'),
      (110, 'snowballs found', 2, 0), 'snowballs added')
    
  def do_ruby(self, x):
    '''ruby [rubies to add] -- adds rubies
    ruby -- prints current and found rubies'''
    self.quantStatCommand(x, (('rubies',), 'current rubies'),
      (102, 'rubies found', 2, 0), 'rubies added')
    
  def do_present(self, x):
    '''present [rubies to add] -- adds presents
    present -- prints presents found'''
    self.quantStatCommand(x, None,
      (111, 'presents found', 2, 0), 'presents added')

  def do_timewarp(self, x):
    '''timewarp [time in seconds] -- will cause the game to process extra offline time when importing the save'''
    x = self.resolveint(x)
    if (x == None): return
    self.save['lastsave'] -= x

  def do_scry(self, x):
    '''maxes production and mana scry timers (and heart, for Valentine event)'''
    for k,v in {'oTimer': 14400, 'oTimer2': 600, 'oTimer3': 14400}.items():
      self.save[k] = v
    print 'All scry timers set to max.'

  def do_edit(self, x):
    '''Edits every available value in the save data.\nType "edit" to see a list of all subcommands.\nType "edit help" to see a list of all subcommands with their options.\n\nWARNING: This command simply assigns values to different structures in the save file. No effort has been made to protect against otherwise impossible data configurations. Always keep a backup copy.'''
    param = x.split()
    # unused save fields: options, buyMode, excavBuyMode, gameVersion, saveVersion, gameVersionRevision

    edithelp = {'_helpheader': 'WARNING: This command simply assigns values to different structures in the save file. No effort has been made to protect against otherwise impossible data configurations. Always keep a backup copy.\n',
                ## subcmds with len(param) == 2
                'reinc':       'use "edit reinc <x>" to set reincarnation count',
                'gems':        'use "edit gems <x>" to set gem count (\'e\' notation is allowed; eg. 1e21)',
                'rubies':      'use "edit rubies <x>" to increase rubies (\'e\' notation is allowed; eg. 1e21)\nuse "edit rubies reset <all/asst/regen/mana/gem/fc>" to reset ruby bonus and refund rubies',
                'art':         'use "edit art seed" to set artifact RNG seed to an extremely low value, virtually ensuring an artifact will be awarded next excavation',
                'eggrng':      'use "edit eggrng <good/x>" to set easter egg RNG seed so you will get the 8 unique eggs in less than 400 egg pick-ups, or use any integer to set it specifically',
                'excav':       'use "edit excav <x>" to set excavations',
                'gold':        'use "edit gold <x>" to set gold amount (\'e\' notation is allowed; eg. 1e21)',
                'mana':        'use "edit mana <x>" to set current mana',
                'ascend':      'use "edit ascend <x>" to set ascension count',
                'wstorm':      'use "edit wstorm <x>" to set time since last storm of wealth, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'titanchrg':   'use "edit titanchrg <x>" to set time left for titans charged clicks/structures, in seconds',
                'greenfngr':   'use "edit greenfngr <x>" to set time since last green fingers discount, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'angeline':    'use "edit angeline <x>" to set time since starting angeline, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'lastclick':   'use "edit lastclick <x>" to set time since last mouse click, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'lastkey':     'use "edit lastkey <x>" to set time since last key press, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'lastmotion':  'use "edit lastmotion <x>" to set time since last mouse motion, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'offline':     'use "edit offline <x>" to increase offline time, in seconds (\'dhms\' notation is allowed; eg. 2d12h17m8s)',
                'ctlfactions': 'use "edit ctlfactions <x>" to set number of factions that have cast Call to Love',
                'eggstack':    'use "edit eggstack <x>" to set number of easter eggs in the stack',
                'lastgift':    'use "edit lastgift <YYYYMMDD>" to set date of last gift',
                'feat':        'use "edit feat <all/thanx/xmas1,2,3,4/valen1,2/easter1,2,3,4>" to toggle feats on or off (note: the "all" switch will only toggle feats on if you have exactly 0, it will toggle feats off if any are incomplete)',
                'quest':       'use "edit quest <all/snow/gift/love/egg1/egg2>" to toggle event questlines complete or not (note: the "all" switch will only toggle quests on if you have exactly 0, it will toggle quests off if any are incomplete)',
                'manabar':     'use "edit manabar <on/off/percentage of mana>" to turn on or off, or set bar at a specific level',
                'ls':          'use "edit ls <none,1-11>" to set current LS target',
                'upgrade':     'use "edit upgrade <upgrade ID>" to toggle upgrades; use bit.do/RGStats to look up IDs',
                'trophy':      'use "edit trophy <numeric ID>" to toggle trophies on or off; use bit.do/RGStats to look up IDs',
                'align':       'use "edit align <none/good/evil/neutral>" to set alignment',
                'season':      'use "edit season <none/thanx/xmas/valen/easter>" to set event season',
                'faction':     'use "edit faction <none/fairy/elf/angel/goblin/undead/demon/titan/druid/faceless/dwarf/drow/merc>" to set faction',
                'prestige':    'use "edit prestige <none/fairy/elf/angel/goblin/undead/demon/titan/druid/faceless/dwarf/drow/merc>" to set prestige faction',
                'bstream':     'use "edit bstream <none/fairy/elf/angel/goblin/undead/demon/titan/druid/faceless/dwarf/drow/merc>" to set faction for bloodstream bonus',
                'bline':       'use "edit bline <none/fairy/elf/angel/goblin/undead/demon/titan/druid/faceless/dwarf/drow>" to set bloodline upgrade (setting bloodline to none will remove bloodstream as well)',
                'research':    'use "edit research <none/short name>" to un-buy all research, or toggle research upgrades on/off (short names: d55 or a25b, etc.)',
                ## subcmds with len(param) == 3
                'scry':        'use "edit scry max" to maximize all the scry timers\nuse "edit scry <all/prod/mana/event> <x>" to set scry timers, in seconds',
                'build':       'use "edit build <all/tier of building> <x>" to set number of buildings',
                'miracle':     'use "edit miracle time <0-120>" to set remaining miracle time, in seconds\nuse "edit miracle tier <1-11>" to set which building miracle is targeting',
                'snowball':    'use "edit snowball <size/scry> <x>" to set snowball size and scry-uses values',
                'evres':       'use "edit evres <all/snow/heart/commonegg/rareegg> <x>" to set event resource amounts',
                'cs':          'use "edit cs <total/streak> <x>" to set combo strike values',
                'fc':          'use "edit fc <all/fairy/elf/angel/goblin/undead/demon/titan/druid/faceless/dwarf/drow/merc> <x> to set FC amounts (\'e\' notation is allowed; eg. 1e21)',
                're':          'use "edit re <all/fairy/elf/angel/goblin/undead/demon/titan/druid/faceless/dwarf/drow/merc> <x> to set RE amounts',
                'mercspell':   'use "edit mercspell <1/2> <tc/cta/hl/fc/mb/gh/bf/gobg/nt/hb/gemg/ls/gb/bw/dp/cs/ss>" to set mercenary spells',
                ## subcmds with len(param) == 4
                'stat':        'use "edit stat <stat ID (0-124)> <game/reinc/all> <x>" to set stat values; use bit.do/RGStats to look up IDs',
                ## subcmds with len(param) == 5
                'spell':       'use "edit spell <short name> <active> <x>" to set seconds spell has been active\nuse "edit spell <short name> <casts/time> <game/reinc/all> <x>" to set # of casts, or total active time (in seconds), for this game, this reinc, or all time\n short names: tc/cta/hl/fc/mb/gh/bf/gobg/nt/hb/gemg/ls/gb/bw/dp/cs/ss'}
    
    editcmds = []
    for k in iter(edithelp):
      editcmds.append(k)
    editcmds.sort()
    if len(param) < 1:
      print edithelp['_helpheader']
      print '"edit" subcommands:'
      for i in editcmds:
        if i == '_helpheader': continue
        elif i == editcmds[-1]: print i
        else: print i+',',
      print '\n(type "edit <subcmd>" to see individual options)'
      print '(type "edit help" to see all subcommands with options)'
      return
    if len(param) >= 2 and self.checksave(): return

    alignSwitch = {'none':0, 'good':1, 'evil':2, 'neutral':3}
    bldgAlignSwitch = {0:[0,1,2], 1:[0,1,2,3,4,5,6,7,8,9,24], 2:[0,1,2,10,11,12,13,14,15,16,24], 3:[0,1,2,17,18,19,20,21,22,23,24]}
    csSwitch = {'total':'comboStrike', 'streak':'comboStrikeCont'}
    evresSwitch = {'snow':0, 'heart':2, 'commonegg':4, 'rareegg':5}
    factionSwitch = {'none':255, 'fairy':0, 'elf':1, 'angel':2, 'goblin':3, 'undead':4, 'demon':5, 'titan':6, 'druid':7, 'faceless':8, 'dwarf':9, 'drow':10, 'merc':11}
    factionSwitch2 = {'fairy':0, 'elf':1, 'angel':2, 'goblin':3, 'undead':4, 'demon':5, 'titan':6, 'druid':7, 'faceless':8, 'dwarf':9, 'drow':10, 'merc':11}
    factionSwitch3 = {'none':None, 'fairy':194, 'elf':164, 'angel':39, 'goblin':212, 'undead':396, 'demon':103, 'titan':380, 'druid':136, 'faceless':183, 'dwarf':150, 'drow':120}
    featSwitch = {'all':[115, 164, 166, 165, 163, 174, 175, 191, 194, 192, 193], 'thanx':115, 'xmas1':164, 'xmas2':166, 'xmas3':165, 'xmas4':163, 'valen1':174, 'valen2':175, 'easter1':191, 'easter2':194, 'easter3':192, 'easter4':193}
    gamestatSwitch = {'game': 'c', 'reinc': 'r', 'all': 'e'}
    gamestatSwitch2 = {'game': 'active0', 'reinc': 'active1', 'all': 'active2'}
    questSwitch = {'all':[116800, 116801, 116802, 116803, 116700, 116701, 116702, 116703, 117600, 117601, 117602, 119500, 119501, 119502, 119503, 119600, 119601, 119602, 119603],
                   'snow':[116800, 116801, 116802, 116803], 'gift':[116700, 116701, 116702, 116703], 'love':[117600, 117601, 117602], 'egg1':[119500, 119501, 119502, 119503], 'egg1':[119600, 119601, 119602, 119603]}
    allResearch = [130300, 129901, 130903, 130002, 130504, 129805, 130806, 130407, 130208, 130110, 130709, 130611, 129712, 144713, 145314, 144915, 145116, 145217, 145018, 144819,
                   153920, 153621, 153722, 153823, 154024, 125300, 125201, 125702, 125903, 125004, 126305, 126106, 126007, 126208, 125409, 125610, 125111, 125812, 142613, 143214,
                   142815, 143116, 142717, 143018, 142919, 151520, 151421, 151622, 151323, 151224, 126400, 127001, 126602, 126803, 127504, 126905, 127206, 127108, 127409, 126507,
                   127610, 127311, 126712, 143813, 143614, 143915, 143316, 143517, 143418, 143719, 152720, 152621, 152922, 153023, 152824, 128100, 128701, 128202, 128403, 127804,
                   128305, 127907, 128806, 128608, 127709, 128510, 128011, 128912, 144413, 144214, 144615, 144516, 144017, 144318, 144119, 153320, 153121, 153522, 153223, 153424,
                   124500, 124801, 124002, 123903, 124304, 124605, 124206, 124907, 123808, 124109, 124710, 123711, 124412, 142313, 142414, 142115, 142216, 141917, 142518, 142019,
                   152420, 152521, 152122, 152323, 152224, 131000, 131501, 132202, 131603, 131204, 132005, 131810, 131909, 131706, 131407, 131108, 131311, 132112, 145413, 145514,
                   145615, 145816, 145717, 146018, 145919, 154120, 154421, 154222, 154323, 154524]
    researchSwitch = {'none': allResearch, 'all':allResearch,
                      's1':[allResearch[0]],   's10':[allResearch[1]],  's30':[allResearch[2]],  's50':[allResearch[3]],  's105':[allResearch[4]],
                      's135':[allResearch[5]], 's150':[allResearch[6]], 's175a':[allResearch[7]], 's175b':[allResearch[8]], 's200':[allResearch[9]],
                      's215':[allResearch[10]], 's225':[allResearch[11]], 's250':[allResearch[12]], 's251':[allResearch[13]], 's270':[allResearch[14]],
                      's300':[allResearch[15]], 's305':[allResearch[16]], 's330':[allResearch[17]], 's375':[allResearch[18]], 's400':[allResearch[19]],
                      's435':[allResearch[20]], 's460':[allResearch[21]], 's500':[allResearch[22]], 's545':[allResearch[23]], 's590':[allResearch[24]],
                      'c1':[allResearch[25]], 'c10':[allResearch[26]], 'c25':[allResearch[27]], 'c50':[allResearch[28]], 'c80':[allResearch[29]],
                      'c105':[allResearch[30]], 'c120':[allResearch[31]], 'c135':[allResearch[32]], 'c150':[allResearch[33]], 'c175':[allResearch[34]],
                      'c200':[allResearch[35]], 'c225':[allResearch[36]], 'c250':[allResearch[37]], 'c251':[allResearch[38]], 'c300':[allResearch[39]],
                      'c305':[allResearch[40]], 'c330':[allResearch[41]], 'c340':[allResearch[42]], 'c375':[allResearch[43]], 'c400':[allResearch[44]],
                      'c405':[allResearch[45]], 'c460':[allResearch[46]], 'c500':[allResearch[47]], 'c520':[allResearch[48]], 'c590':[allResearch[49]],
                      'd1':[allResearch[50]], 'd10':[allResearch[51]], 'd25':[allResearch[52]], 'd50':[allResearch[53]], 'd55':[allResearch[54]],
                      'd135':[allResearch[55]], 'd150':[allResearch[56]], 'd175':[allResearch[57]], 'd200':[allResearch[58]], 'd205':[allResearch[59]],
                      'd225':[allResearch[60]], 'd245':[allResearch[61]], 'd250':[allResearch[62]], 'd260':[allResearch[63]], 'd275':[allResearch[64]],
                      'd290':[allResearch[65]], 'd320':[allResearch[66]], 'd330':[allResearch[67]], 'd350':[allResearch[68]], 'd400':[allResearch[69]],
                      'd435':[allResearch[70]], 'd480':[allResearch[71]], 'd525':[allResearch[72]], 'd560':[allResearch[73]], 'd590':[allResearch[74]],
                      'e1':[allResearch[75]], 'e10':[allResearch[76]], 'e25':[allResearch[77]], 'e30':[allResearch[78]], 'e50':[allResearch[79]],
                      'e80':[allResearch[80]], 'e135':[allResearch[81]], 'e145':[allResearch[82]], 'e150':[allResearch[83]], 'e200':[allResearch[84]],
                      'e225a':[allResearch[85]], 'e225b':[allResearch[86]], 'e250':[allResearch[87]], 'e260':[allResearch[88]], 'e275':[allResearch[89]],
                      'e290':[allResearch[90]], 'e320':[allResearch[91]], 'e330':[allResearch[92]], 'e350':[allResearch[93]], 'e400':[allResearch[94]],
                      'e410':[allResearch[95]], 'e460':[allResearch[96]], 'e480':[allResearch[97]], 'e495':[allResearch[98]], 'e590':[allResearch[99]],
                      'a1':[allResearch[100]], 'a10':[allResearch[101]], 'a25a':[allResearch[102]], 'a25b':[allResearch[103]], 'a50':[allResearch[104]],
                      'a55':[allResearch[105]], 'a105':[allResearch[106]], 'a120':[allResearch[107]], 'a135':[allResearch[108]], 'a150':[allResearch[109]],
                      'a175':[allResearch[110]], 'a200':[allResearch[111]], 'a250':[allResearch[112]], 'a251':[allResearch[113]], 'a270':[allResearch[114]],
                      'a300':[allResearch[115]], 'a305':[allResearch[116]], 'a330':[allResearch[117]], 'a375':[allResearch[118]], 'a400':[allResearch[119]],
                      'a410':[allResearch[120]], 'a460':[allResearch[121]], 'a480':[allResearch[122]], 'a495':[allResearch[123]], 'a590':[allResearch[124]],
                      'w1':[allResearch[125]], 'w10':[allResearch[126]], 'w25':[allResearch[127]], 'w50':[allResearch[128]], 'w120':[allResearch[129]],
                      'w135':[allResearch[130]], 'w150':[allResearch[131]], 'w175':[allResearch[132]], 'w180':[allResearch[133]], 'w200':[allResearch[134]],
                      'w205':[allResearch[135]], 'w225':[allResearch[136]], 'w250':[allResearch[137]], 'w260':[allResearch[138]], 'w275':[allResearch[139]],
                      'w290':[allResearch[140]], 'w320':[allResearch[141]], 'w330':[allResearch[142]], 'w350':[allResearch[143]], 'w400':[allResearch[144]],
                      'w405':[allResearch[145]], 'w520':[allResearch[146]], 'w525':[allResearch[147]], 'w560':[allResearch[148]], 'w590':[allResearch[149]]}
    rubySwitch = {'asst':105, 'regen':106, 'mana':107, 'gem':108, 'fc':109}
    seasonSwitch = {'none':0, 'thanx':1, 'xmas':2, 'valen':3, 'easter':4}
    spellIDs = {'tc':18, 'cta':3, 'hl':12, 'fc':6, 'mb':14, 'gh':9, 'bf':1, 'gobg':8, 'nt':15, 'hb':11, 'gemg':7, 'ls':13, 'gb':10, 'bw':2, 'dp':5, 'cs':4, 'ss':17}
    spellSwitch = {'tc':0, 'cta':1, 'hl':2, 'fc':3, 'mb':4, 'gh':5, 'bf':6, 'gobg':7, 'nt':8, 'hb':9, 'gemg':10, 'ls':11, 'gb':12, 'bw':13, 'dp':14, 'cs':15, 'ss':16}
    statSwitch = {'game':'stats', 'reinc':'statsReset', 'all':'statsRei'}
    units = {'d':0, 'h':0, 'm':0 , 's':0}

    try:
      if param[0] == 'help':
        for i in editcmds: print edithelp[i]
      elif param[0] == 'align':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in alignSwitch:
          self.save['alignment'] = alignSwitch[param[1]]
          print 'set alignment to', param[1]
        else: raise ValueError
      elif param[0] == 'angeline':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          self.save['sTimer'] = int(param[1])*30
          print 'set angeline time to', self.save['sTimer']/30, 'seconds'
      elif param[0] == 'art':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] == 'seed':
          self.save['artifactRngState'] = 1407677000
          print 'set artifact RNG state to', self.save['artifactRngState']
      elif param[0] == 'ascend':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['ascension'] = int(param[1])
          print 'set ascension count to', self.save['ascension']
      elif param[0] == 'bline':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in factionSwitch3:
          if param[1] == 'none':
            for e in self.save['upgrade']:
              if e['_id'] in [194, 164, 39, 212, 396, 103, 380, 136, 183, 150, 120, 13, 327]:
                e['u1'] = False
                print 'set bloodline to', param[1]
          else:
            for e in self.save['upgrade']:
              if e['_id'] in [194, 164, 39, 212, 396, 103, 380, 136, 183, 150, 120]:
                e['_id'] = factionSwitch3[param[1]]
                print 'set bloodline to', param[1]
        else: raise ValueError
      elif param[0] == 'bstream':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in factionSwitch:
          self.save['bFaction'] = factionSwitch[param[1]]
          print 'set bloodstream bonus faction to', param[1]
        else: raise ValueError
      elif param[0] == 'build':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[1] == 'all':
            for b in bldgAlignSwitch[self.save['alignment']]:
              self.save['build'][b]['q'] = int(param[2])
            print 'set number of all buildings to', self.save['build'][0]['q']
          elif param[1] in ['1','2','3','4','5','6','7','8','9','10','11']:
            b = bldgAlignSwitch[self.save['alignment']][int(param[1])-1]
            self.save['build'][b]['q'] = int(param[2])
            print 'set number of tier', param[1], 'buildings to', self.save['build'][b]['q']
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'cs':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[1] in csSwitch:
            self.save[csSwitch[param[1]]] = int(param[2])
            print 'set combo strike', param[1], 'by', self.save[csSwitch[param[1]]]
        else: raise ValueError
      elif param[0] == 'ctlfactions':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['ctaFactionCasts'] = int(param[1])
          print 'set # of factions cast Call to Love to', self.save['ctaFactionCasts']
      elif param[0] == 'eggrng':
        if len(param) == 1: print edithelp[param[0]]
        else:
          if param[1] == 'good':
            self.save['eggRngState'] = 873457390
          else: self.save['eggRngState'] = int(param[1])
          print 'set easter egg RNG state to', self.save['eggRngState']
      elif param[0] == 'eggstack':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['eggStackSize'] = int(param[1])
          print 'set # of easter eggs in stack to', self.save['eggStackSize']
      elif param[0] == 'evres':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[1] == 'all':
            self.save['extraResources'] = [int(param[2])]*4
            print 'set all event resources to', self.save['extraResources'][0]
          elif param[1] in evresSwitch:
            if param[1] == 'commonegg':
              self.save['stats'][123] = int(param[2])
            elif param[1] == 'rareegg':
              self.save['stats'][124] = int(param[2])
            self.save['extraResources'][evresSwitch[param[1]]] = int(param[2])
            print 'set', param[1], 'resources to', self.save['extraResources'][evresSwitch[param[1]]]
        else: raise ValueError
      elif param[0] == 'excav':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['excavations'] = int(param[1])
          print 'set excavations to', self.save['excavations']
      elif param[0] == 'faction':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in factionSwitch:
          self.save['faction'] = factionSwitch[param[1]]
          print 'set faction to', param[1]
        else: raise ValueError
      elif param[0] == 'fc':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if 'e' in param[2]:
            param[2] = param[2].split('e')
            if len(param[2]) >= 2: param[2] = int(param[2][0])*10**int(param[2][1])
          if param[1] in 'all':
            self.save['secondaryResources'] = [int(param[2])]*12
            print 'set all faction FCs to', self.save['secondaryResources'][0]
          elif param[1] in factionSwitch2:
            self.save['secondaryResources'][factionSwitch2[param[1]]] = int(param[2])
            print 'set', param[1], 'FCs to', self.save['secondaryResources'][factionSwitch2[param[1]]]
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'feat':
        if len(param) == 1: print edithelp[param[0]]
        else:
          if param[1] in featSwitch:
            foundFeats = []
            for e in self.save['trophy']:
              if e['_id'] in featSwitch['all']: foundFeats.append(e)
            if param[1] == 'all':
              if len(foundFeats) == 0:
                for f in featSwitch['all']:
                  self.save['trophy'].append({'_id':f})
                print 'set all feats to', True
              else:
                for f in foundFeats:
                  self.save['trophy'].remove(f)
                print 'set all feats to', False
            else:
              removedFeat = False
              for e in self.save['trophy']:
                if e['_id'] == featSwitch[param[1]]:
                  removedFeat = True
                  self.save['trophy'].remove(e)
                  print 'removed feat', param[1]
              if not removedFeat:
                self.save['trophy'].append({'_id':featSwitch[param[1]]})
                print 'added feat', param[1]
          else: raise ValueError
      elif param[0] == 'gems':
        if len(param) == 1: print edithelp[param[0]]
        else:
          if 'e' in param[1]:
            param[1] = param[1].split('e')
            if len(param[1]) >= 2: param[1] = int(param[1][0])*10**int(param[1][1])
          self.save['gems'] = int(param[1])
          print 'set gem count to', self.save['gems']
      elif param[0] == 'gold':
        if len(param) == 1: print edithelp[param[0]]
        else:
          if 'e' in param[1]:
            param[1] = param[1].split('e')
            if len(param[1]) >= 2: param[1] = int(param[1][0])*10**int(param[1][1])
          self.save['resource'] = int(param[1])
          print 'set gold amount to', self.save['resource']
      elif param[0] == 'greenfngr':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          self.save['goblinTimer'] = int(param[1])
          print 'set time since last green fingers discount to', self.save['goblinTimer'], 'seconds'
      elif param[0] == 'lastclick':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          self.save['cTimer'] = int(param[1])*30
          print 'set time since last mouse click to', self.save['cTimer']/30, 'seconds'
      elif param[0] == 'lastgift':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param[1]) == 8:
          self.save['lastGiftDate'] = int(param[1])
          print 'set last gift date to', param[1]
        else: raise ValueError
      elif param[0] == 'lastkey':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          self.save['kcTimer'] = int(param[1])*30
          print 'set time since last key press to', self.save['kcTimer']/30, 'seconds'
      elif param[0] == 'lastmotion':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          self.save['mTimer'] = int(param[1])*30
          print 'set time since last mouse motion to', self.save['mTimer']/30, 'seconds'
      elif param[0] == 'ls':
        if len(param) == 1: print edithelp[param[0]]
        elif 1 <= int(param[1]) <= 11:
          self.save['strikeTier'] = int(param[1])
          print 'set current LS target to tier', self.save['strikeTier']
        elif param[1] == 'none':
          self.save['strikeTier'] = 255
          print 'set current LS target to none'
        else: raise ValueError
      elif param[0] == 'mana':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['mana'] = int(param[1])
          print 'set current mana to', self.save['mana']
      elif param[0] == 'manabar':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] == 'on':
          self.save['cont'] = True
          print 'set manabar on'
        elif param[1] == 'off':
          self.save['cont'] = False
          print 'set manabar off'
        elif 0 <= float(param[1]) <= 100.0:
          self.save['contv'] = float(param[1])
          print 'set manabar to', str(self.save['contv'])+'%'
        else: raise ValueError
      elif param[0] == 'mercspell':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[2] in spellIDs:
            if param[1] == '1':
              self.save['msp'] = spellIDs[param[2]]
              print 'set 1st mercenary spell to', param[2]
            elif param[1] == '2':
              self.save['msp2'] = spellIDs[param[2]]
              print 'set 2nd mercenary spell to', param[2]
            else: raise ValueError
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'miracle':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[1] == 'time':
            if 0 <= int(param[2]) <= 120:
              self.save['miracleTimer'] = int(param[2])
              print 'set miracle time left to', self.save['miracleTimer'], 'seconds'
            else: raise ValueError
          elif param[1] == 'tier':
            if 1 <= int(param[2]) <= 11:
              self.save['miracleTier'] = int(param[2])
              print 'set miracle tier to', self.save['miracleTier']
            else: raise ValueError
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'offline':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          oldtime = self.save['lastsave']
          self.save['lastsave'] -= int(param[1])
          print 'increased offline time by', oldtime - self.save['lastsave'], 'seconds'
      elif param[0] == 'prestige':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in factionSwitch:
          self.save['activeFaction'] = factionSwitch[param[1]]
          print 'set prestige faction to', param[1]
        else: raise ValueError
      elif param[0] == 'quest':
        if len(param) == 1: print edithelp[param[0]]
        else:
          if param[1] in questSwitch:
            foundQuests = []
            for e in self.save['trophy']:
              if e['_id'] in questSwitch['all']: foundQuests.append(e)
            if param[1] == 'all':
              if len(foundQuests) == 0:
                for q in questSwitch['all']:
                  self.save['trophy'].append({'_id':q})
                print 'set all questlines to', True
              else:
                for q in foundQuests:
                  self.save['trophy'].remove(q)
                print 'set all questlines to', False
            else:
              fullQuestline = True
              for q in questSwitch[param[1]]:
                if {'_id':q} not in foundQuests:
                  fullQuestline = False
              if fullQuestline:
                for q in questSwitch[param[1]]:
                  self.save['trophy'].remove({'_id':q})
                print 'removed questline', param[1]
              else:
                for q in questSwitch[param[1]]:
                  if {'_id':q} not in self.save['trophy']:
                    self.save['trophy'].append({'_id':q})
                print 'added complete questline', param[1]
          else: raise ValueError
      elif param[0] == 're':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[1] == 'all':
            self.save['royalExchangeFaction'] = [int(param[2])]*12
            print 'set all faction REs to', self.save['royalExchangeFaction'][0]
          elif param[1] in factionSwitch2:
            self.save['royalExchangeFaction'][factionSwitch2[param[1]]] = reAmount
            print 'set', param[1], 'REs to', self.save['royalExchangeFaction'][factionSwitch2[param[1]]]
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'reinc':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['rei'] = int(param[1])
          print 'set reincarnation count to', self.save['rei']
      elif param[0] == 'research':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in researchSwitch:
          toggleFlag = False
          for e in researchSwitch[param[1]]:
            for i in self.save['upgrade']:
              if i['_id'] == e:
                if i['u1']:
                  if param[1] != 'all':
                    i['u1'] = False
                    print 'set research', e,'to', i['u1']
                    toggleFlag = True
                else:
                  if param[1] != 'none':
                    i['u1'] = True
                    print 'set research', e,'to', i['u1']
                    toggleFlag = True
          if not toggleFlag:
            if param[1] != 'none':
              self.save['upgrade'].append({'_id':researchSwitch[param[1]][0], 'u1':True, 's':0})
              print 'unlocked research', param[1], 'and set to',True
        else: raise ValueError
      elif param[0] == 'rubies':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) == 2:
          if 'e' in param[1]:
            param[1] = param[1].split('e')
            if len(param[1]) >= 2: param[1] = int(param[1][0])*10**int(param[1][1])
          self.save['rubies'] += int(param[1])
          self.save['stats'][102] += int(param[1])
          print 'increased rubies to', self.save['rubies']
        elif (len(param) >= 3) and (param[1] == 'reset'):
          if param[2] == 'all':
            rubyRefund = 0
            for i in range(105,110):
              bonusLvl = self.save['stats'][i] + self.save['statsReset'][i] + self.save['statsRei'][i]
              rubyRefund += bonusLvl * (bonusLvl + 1) / 2
            self.save['rubies'] += rubyRefund
            self.save['statsRei'][105] = self.save['statsReset'][105] = self.save['stats'][105] = self.save['statsRei'][106] = self.save['statsReset'][106] = self.save['stats'][106] = self.save['statsRei'][107] = self.save['statsReset'][107] = self.save['stats'][107] = self.save['statsRei'][108] = self.save['statsReset'][108] = self.save['stats'][108] = self.save['statsRei'][109] = self.save['statsReset'][109] = self.save['stats'][109] = 0
            print 'reset all ruby bonuses to', self.save['statsRei'][105], 'and refunded', rubyRefund, 'rubies'
          elif param[2] in rubySwitch:
            bonusLvl = self.save['stats'][rubySwitch[param[2]]] + self.save['statsReset'][rubySwitch[param[2]]] + self.save['statsRei'][rubySwitch[param[2]]]
            rubyRefund = bonusLvl * (bonusLvl + 1) / 2
            self.save['rubies'] += rubyRefund
            self.save['statsRei'][bonusSwitch[param[2]]] = self.save['statsReset'][bonusSwitch[param[2]]] = self.save['stats'][bonusSwitch[param[2]]] = 0
            print 'reset', param[2], 'ruby bonus to', self.save['statsRei'][bonusSwitch[param[2]]], 'and refunded', rubyRefund, 'rubies'
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'scry':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) == 2:
          if param[1] == 'max':
            self.save['oTimer'] = 14400
            self.save['oTimer2'] = 600
            self.save['oTimer3'] = 14400
            print 'set all scry timers to max'
          else: raise ValueError
        elif len(param) >= 3:
          if param[1] == 'all':
            self.save['oTimer'] = int(param[2])
            self.save['oTimer2'] = int(param[2])
            self.save['oTimer3'] = int(param[2])
            print 'set all scry timers to', self.save['oTimer'], 'seconds'
          elif param[1] == 'prod':
            self.save['oTimer'] = int(param[2])
            print 'set production scry timer to', self.save['oTimer'], 'seconds'
          elif param[1] == 'mana':
            self.save['oTimer2'] = int(param[2])
            print 'set mana scry timer to', self.save['oTimer2'], 'seconds'
          elif param[1] == 'event':
            self.save['oTimer3'] = int(param[2])
            print 'set event scry timer to', self.save['oTimer3'], 'seconds'
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'season':
        if len(param) == 1:
          print edithelp[param[0]]
        elif param[1] in seasonSwitch:
          self.save['season'] = seasons[param[1]]
          print 'set season to:', seasonkeys[self.save['season']]
        else: raise ValueError
      elif param[0] == 'snowball':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 3:
          if param[1] == 'size':
            self.save['snowballSize'] = int(param[2])
            print 'set snowball size to', self.save['snowballSize']
          elif param[1] == 'scry':
            if 0 <= int(param[2]) <= 5:
              self.save['snowballScryUses'] = int(param[2])
              print 'set number of snowball scry used to:', self.save['snowballScryUses']
            else: raise ValueError
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'spell':
        if len(param) == 1: print edithelp[param[0]]
        elif param[1] in spellSwitch:
          if len(param) == 4:
            if param[2] == 'active':
              self.save['spell'][spellSwitch[param[1]]]['t'] = int(param[3])*30
              print 'set', param[1], 'active for', self.save['spell'][spellSwitch[param[1]]]['t']/30, 'seconds'
            else: raise ValueError
          elif len(param) >= 5:
            if param[2] == 'casts':
              self.save['spell'][spellSwitch[param[1]]][gamestatSwitch[param[3]]] = int(param[4])
              print 'set', param[1], 'cast count to', self.save['spell'][spellSwitch[param[1]]][gamestatSwitch[param[3]]]
            elif param[2] == 'time':
              self.save['spell'][spellSwitch[param[1]]][gamestatSwitch2[param[3]]] = int(param[4])
              print 'set', param[1], 'total active time to', self.save['spell'][spellSwitch[param[1]]][gamestatSwitch2[param[3]]]
            else: raise ValueError
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'stat':
        if len(param) == 1: print edithelp[param[0]]
        elif len(param) >= 4:
          if (0 <= int(param[1]) <= 124) and (param[2] in statSwitch):
            self.save[statSwitch[param[2]]][int(param[1])] = int(param[3])
            print 'set stat #', param[1], 'to', self.save[statSwitch[param[2]]][int(param[1])]
          else: raise ValueError
        else: raise ValueError
      elif param[0] == 'titanchrg':
        if len(param) == 1: print edithelp[param[0]]
        else:
          self.save['chargedTimer'] = int(param[1])*30
          print 'set time left for titan charges', self.save['chargedTimer']/30, 'seconds'
      elif param[0] == 'trophy':
        if len(param) == 1: print edithelp[param[0]]
        else:
          didRemove = False
          for t in self.save['trophy']:
            if t['_id'] == int(param[1]):
              self.save['trophy'].remove(t)
              print 'removed trophy #', t['_id']
              didRemove = True
          if not didRemove:
            self.save['trophy'].append({'_id':int(param[1])})
            print 'added trophy #', param[1]
      elif param[0] == 'upgrade':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for i in self.save['upgrade']:
            if i['_id'] == int(param[1]):
              if i['u1']:
                i['u1'] = False
                print 'set upgrade #', param[1],'to', i['u1']
              else:
                i['u1'] = True
                print 'set upgrade #', param[1],'to', i['u1']
              return
          print 'upgrade not found; in-game requirements not met or exclusionary choices made'
      elif param[0] == 'wstorm':
        if len(param) == 1: print edithelp[param[0]]
        else:
          for unit in ['d', 'h', 'm', 's']:
            if unit in param[1]:
              param[1] = param[1].split(unit)
              units[unit] = int(param[1][0])
              param[1] = param[1][1]
          if [units['d'], units['h'], units['m'], units['s']] != [0, 0, 0, 0]:
            param[1] = units['d']*24*60*60 + units['h']*60*60 + units['m']*60 + units['s']
          self.save['somethingNew'] = int(param[1])
          print 'set time since last storm of wealth to', self.save['somethingNew'], 'seconds'
      else:
        self.do_edit('')
    except ValueError: print 'invalid parameter(s) used'
        
##ea = EditAssist()
##ea.cmdloop()

class App:

    def __init__(self, master):

        frame = Frame(master)
        frame.pack()

        self.button = Button(
            frame, text="QUIT", fg="red", command=frame.quit
            )
        self.button.pack(side=LEFT)

        self.hi_there = Button(frame, text="Hello", command=self.say_hi)
        self.hi_there.pack(side=LEFT)

    def say_hi(self):
        print "hi there, everyone!"

root = Tk()

app = App(root)
root.mainloop()
