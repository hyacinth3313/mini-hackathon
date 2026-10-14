# sample.py - planted problems for testing detectors.py

class BadClass:
    pass  # Missing docstring

def messy_function(a, b, c, d, e, f):
    # Missing docstring, 6 parameters (too many parameters)
    unused_variable = 99  # Unused variable
    
    # Deep nesting (>3 levels)
    if a > 0:
        for i in range(b):
            while c > 0:
                try:
                    d -= 1
                except:
                    pass

    # Padding to make the function >30 lines (function too long)
    x = 0
    for _ in range(35):
        x += 1
    return x