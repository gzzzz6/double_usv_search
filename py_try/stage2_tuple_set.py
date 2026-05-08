#题目1
point = (10,20)
print(point[0])
print(point[1])

#题目2
weekdays = ("周一","周二","周三","周四","周五")
for day in weekdays:
    print(day)

#题目3
a = (10)
b = (10,)
print(type(a))
print(type(b))

#题目4
names = ["张三", "李四", "张三", "王五", "李四"]
new_names = set(names)
print(new_names)

#题目5
numbers = {1,2,3}
numbers.add(4)
numbers.remove(2)
numbers.discard(100)
print(numbers)

#题目6
a = {1, 2, 3, 4}
b = {3, 4, 5, 6}
print(f"交集：{a & b}")
print(f"并集：{a | b}")
print(f"差集：{a-b}")
