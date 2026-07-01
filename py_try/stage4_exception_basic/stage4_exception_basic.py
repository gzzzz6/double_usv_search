try:
    print(10/0)
except:
    print("除数不能为0")

try:
    num = int("abc")
except ValueError:
    print("不能把abc转成整数")

try:
    num = int("123")
except ValueError:
    print("转换失败")
else:
    print("转换成功")

try:
    print("开始读取")
    x = int("abc")
except ValueError:
    print("读取失败")
finally:
    print("程序结束")

try:
    with open(r"F:\pythonprojects\py_try\not_exist.txt","r",encoding="utf-8") as file:
        file.read()
except:
    print("文件不存在")

try:
    num = int("0")
    result = 10 / num
except ValueError:
    print("转换失败")
except ZeroDivisionError:
    print("除数不能为0")


