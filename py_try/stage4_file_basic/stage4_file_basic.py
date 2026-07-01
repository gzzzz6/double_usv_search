file_path = r"F:\pythonprojects\py_try\stage4_file_basic\study_note.txt"

with open(file_path,"w",encoding="utf-8") as file:
    file.write("Python学习开始了\n")

with open(file_path,"a",encoding="utf-8") as file:
    file.write("我正在学习文件读写\n")

with open("study_note.txt","r",encoding="utf-8") as file:
    content = file.read()
    print(content)

with open("study_note.txt","a",encoding="utf-8") as file:
    file.write("今天学习了open和with\n")

with open("study_note.txt","r",encoding="utf-8") as file:
    content = file.read()
    print(content)

score_file = r"F:\pythonprojects\py_try\stage4_file_basic\scores.txt"

with open(score_file,"w",encoding="utf-8") as file:
    file.write("张三 88\n")
    file.write("李四 92\n")
    file.write("王五 75\n")

with open("scores.txt","r",encoding="utf-8") as file:
    lines = file.readlines()
    print(lines)
    print(len(lines))
    for line in lines:
        print(line.strip())
    



