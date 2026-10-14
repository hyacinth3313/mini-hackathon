# sample.py - comprehensive test file for detectors.py

class BadClass:
    pass  # Missing class docstring

def messy_function(a, b, c, d, e, f):
    # 1. Missing function docstring
    # 2. Too many parameters (6 parameters > 5)
    
    unused_variable = 99  # 3. Unused variable
    
    # 4. Deep nesting (>3 levels deep)
    if a > 0:
        for i in range(b):
            while c > 0:
                try:
                    d -= 1
                except:
                    pass

    # 5. Function too long (adding extra padding lines to push length > 30)
    x = 0
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    x += 1
    return x