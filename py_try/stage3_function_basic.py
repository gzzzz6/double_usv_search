#题目1
def say_hello():
    print("你好,python")
say_hello()

#题目2
def greet(name):
    print(f"你好，{name}")
greet("张三")
greet("李四")

#题目3
def add(a,b):
    return a+b
result = add(10,20)
print(result)

#题目4
def clac_average(scores):
    average = sum(scores)/len(scores)
    return average
scores = [88,92,75]
print(clac_average(scores))

#题目5
def count_pass(scores):
    count = 0
    for score in scores:
        if score >= 60:
            count = count+1
    return count
scores = [88, 45, 92, 59, 76]
print(count_pass(scores))

#题目6
def introduce(name,city="北京"):
    print(f"我叫{name}，来自{city}")
introduce("张三")
introduce("李四","上海")

#题目7
def show_info(name,age,score):
    print(f"姓名：{name}，年龄：{age}，成绩：{score}")
show_info(score=88,name="张三",age=20)
