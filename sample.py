import math

class BadClass:
    def sample_method(self, a, b, c, d, e):
        return a + b + c + d + e

def messy_function(a, b, c, d, e, f, items=[]):
    unused_variable = 99
    closure_val = 10

    def nested_helper():
        inner_unused = 42
        return closure_val

    if a == 1:
        res = 1
    elif a == 2:
        res = 2
    elif a == 3:
        res = 3
    elif a == 4:
        res = 4
    else:
        res = 5

    with open("temp.txt", "w") as fh:
        if a > 0:
            for i in range(b):
                while c > 0:
                    try:
                        d -= 1
                    except:
                        pass

    pad_1 = res
    pad_2 = pad_1
    pad_3 = pad_2
    pad_4 = pad_3
    pad_5 = pad_4
    pad_6 = pad_5
    pad_7 = pad_6
    pad_8 = pad_7
    pad_9 = pad_8
    pad_10 = pad_9
    pad_11 = pad_10
    pad_12 = pad_11
    pad_13 = pad_12
    pad_14 = pad_13
    pad_15 = pad_14
    return nested_helper() + pad_15

async def async_worker():
    pass