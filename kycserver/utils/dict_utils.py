
from .type_utils import isList, isString


def isDict(obj, nonEmpty=True, keys=[]):
    if type(obj) == dict:
        if nonEmpty:
            if len(obj.keys()) > 0:
                if isList(keys, allValidFunc=isString):
                    necessary_key_set = set(keys)
                    obj_key_set = set(obj.keys())
                    return necessary_key_set <= obj_key_set
                else:
                    return True
            else:
                return False
        else:
            return True
    else:
        return False

def overrideDict(changeDict, oldDict={}, newDictFlag=True):
    """
        Needs Refactoring to account for edge cases
    """
    newDict = None
    if newDictFlag:
        newDict = {}
        if isDict(oldDict):
            for key, val in oldDict.items():
                newDict[key] = val
    if isDict(newDict, False):
        if isDict(changeDict):
            for key, val in changeDict.items():
                newDict[key] = val
        return newDict
    else:
        if isDict(changeDict):
            for key, val in changeDict.items():
                oldDict[key] = val
        return oldDict
    
def copyDict(inital={}, *args):
    cur_dict = overrideDict(inital)
    for new_obj in args:
        if isDict(new_obj):
            overrideDict(new_obj, cur_dict, False)
        else:
            continue
    return cur_dict

def mergeDict(obj1, obj2):
    return overrideDict(obj1, obj2, True)

def dictToStr(obj, sep="\n", prefix=""):
    if isDict(obj):
        str_rep = ""
        for key, val in obj.items():
            str_rep += prefix
            if isDict(val):
                tmp_prefix = f"{prefix}\t"
                str_rep += f"{key} => \n{dictToStr(val, prefix=tmp_prefix)}{sep}"
            else:
                str_rep += f"{key} => {val}{sep}"
        return str_rep
    else:
        if type(obj) == dict:
            return ""
        else:
            raise TypeError(f"Expect a Dictionary, instead got: {type(obj)}")
        
def compareDicts(obj1, obj2, name1="a", name2="b"):
    if isDict(obj1) and isDict(obj2):
        compDict = {}
        for k, v in obj1.items():
            new_v = obj2.get(k, None)
            if v == new_v:
                continue
            else:
                cur_a = compDict.get(name1, {})
                cur_b = compDict.get(name2, {})
                cur_a[k] = v
                cur_b[k] = new_v
                compDict[name1] = cur_a
                compDict[name2] = cur_b
        return compDict
    else:
        raise TypeError(f"Can only be used to compare two dicts")