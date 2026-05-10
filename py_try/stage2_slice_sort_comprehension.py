#题目1
nums = [10, 20, 30, 40, 50, 60]
print(nums[1:4])
print(nums[:3])
print(nums[3:])
print(nums[::-1])

#题目2
print(nums[::2])
print(nums[1::2])

#题目3
scores = [88, 60, 100, 75, 92]
new_scores = sorted(scores)
print(scores)
print(new_scores)
scores.sort()
print(scores)

scores.sort(reverse=True)
print(scores)

#题目4
students = [
    {"name": "张三", "score": 88},
    {"name": "李四", "score": 92},
    {"name": "王五", "score": 75}
]
students.sort(key=lambda student:student["score"],reverse=True)
print(students)

#题目5
nums = [1,2,3,4,5]
# new_nums = []
# for number in nums:
#     new_nums.append(number*number)
new_nums = [number*number for number in nums]
print(new_nums)

#题目6
nums = [1, 2, 3, 4, 5, 6]
# ous = []
# for n in nums:
#     if n%2 == 0 :
#         ous.append(n)
ous = [n for n in nums if n%2==0]
print(ous)

#题目7
scores = [88, 45, 92, 59, 76, 100]
# qualified = []
# for score in scores:
#     if score >= 60 :
#         qualified.append(score)
qualified = [score for score in scores if score>=60]
print(qualified)
