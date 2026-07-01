#题目1
school = "清华大学"
def show_school():
    print(school)
show_school()

#题目2
def test_local():
    local_num = 100
    print(local_num)
test_local()

#题目3
def multiply(a,b):
    num = a*b 
    return num
print(multiply(3,4))

#题目4
def power(num,exponent=2):
    number = num **exponent
    return number
print(power(3))
print(power(2,3))

#题目5
def show_student(name,age,city):
    print(f"{name},{age},{city}")
show_student(age=18,city="北京",name="gzzzz")

#题目6
def calc_total(scores):
    num = sum(scores)
    return num
scores = [99,81,100]
print(calc_total(scores))

#题目7
def calc_average(scores):
    average = sum(scores)/len(scores)
    return average
print(calc_average(scores))

#题目8
def count_pass(scores):
    count = 0
    for score in scores:
        if score >= 60:
            count = count+1
    return count
print(count_pass(scores))

#题目9
scores = [88,45,92,76,59]
print(calc_total(scores))
print(calc_average(scores))
print(count_pass(scores))
