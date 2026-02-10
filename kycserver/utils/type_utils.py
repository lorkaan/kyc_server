
def isString(val, minLength=1):
    if type(val) == str and len(val) >= minLength:
        return True
    else:
        return False
    
def isInteger(val, validatorFunc=None):
    if type(val) == int:
        if callable(validatorFunc):
            return validatorFunc(val)
        else:
            return True
    else:
        return False
    
def isFloat(val, validatorFunc=None):
    if type(val) == float:
        if callable(validatorFunc):
            return validatorFunc(val)
        else:
            return True
    else:
        return False
    
def isNumber(val, validatorFunc=None):
    return isInteger(val, validatorFunc) or isFloat(val, validatorFunc)
     
def isList(val, minLen=1, allValidFunc=None, anyValidFunc=None):
    if type(val) == list and len(val) >= minLen:
        allValid = True
        anyValid = True
        if callable(allValidFunc):
            allValid = all(allValidFunc(x) for x in val)
        if callable(anyValidFunc):
            anyValid = any(anyValidFunc(x) for x in val)
        return allValid and anyValid
    else:
        return False
