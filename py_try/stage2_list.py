import numpy as np


#题目1
names = ["张三","李四","王五"]
print(names)
print(names[0])
print(names[1])
print(names[2])

#题目2
names[1]="赵六"
print(names)

#题目3
fruits = ["苹果", "香蕉", "橘子"]
fruits.append("西瓜")
fruits.remove("香蕉")
print(fruits)

#题目4
scores = [88, 92, 75, 60, 100]
total = 0
total = sum(scores)
print(f"总分：{total}")

max_score = max(scores)

min_score = min(scores)

average = np.mean(scores)

print(f"最高分：{max_score}")
print(f"最低分：{min_score}")
print(f"平均分：{average}")

#题目5
for i,score in enumerate(scores):
    print(f"第{i+1}个成绩是：{score}")

#题目6
scores = [88, 45, 92, 59, 76, 100]
count = 0
for score in scores:
    if score >= 60:
        count = count + 1
print(f"及格人数：{count}")
