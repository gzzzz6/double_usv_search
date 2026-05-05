#题目1
student = {
    "name":"张三",
    "age":20,
    "score":88
}
print(student["name"])
print(student["age"])
print(student["score"])

#题目2
student["score"] = 95
print(student)

#题目3
student["city"] = "北京"
student.pop("age")
print(student)

#题目4
print(student.get("score"))
print(student.get("phone","暂无手机号"))

#题目5
for key,value in student.items():
    print(f"{key}:{value}")

#题目6
students = [
    {
        "name":"张三",
        "score":88
    },
    {
        "name":"李四",
        "score":92
    },
    {
        "name":"王五",
        "score":75
    }
]
total = 0
for student in students:
    print(f"{student["name"]}的成绩是：{student["score"]}")
    total = total + student["score"]
average = total/len(students)
print(average)

