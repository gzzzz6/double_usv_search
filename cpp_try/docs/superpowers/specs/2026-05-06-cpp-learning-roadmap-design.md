# C++ 学习路线设计

## 目标与背景

- 学习者：Python 熟练，C 基础较浅（指针/内存管理了解不多）
- 目标：实用导向——能用 C++ 写高性能计算/算法（GP 模型、路径规划）
- 时间：灵活，不设期限
- 方式：先讲原理 → 再给练习 → 代码验证

## 总体路线：三阶段螺旋推进

每个阶段围绕一个主题从原理到实战深入一层。基础（方案 A）内容融入各阶段。

---

## 阶段一：值语义与内存模型

### 目标
理解 C++ 与 Python 最大的思维差异：Python 一切都是引用，C++ 一切都是值。

### 知识点

**1.1 编译与链接**
- 预处理 → 编译 → 汇编 → 链接
- 头文件的本质（`#include` = 文本替换）、include guard
- `.cpp` → `.o` → 可执行文件，符号解析

**1.2 栈与堆**
- 栈：自动管理，函数返回释放，大小有限（~8MB）
- 堆：`new`/`delete` 手动管理，与 `malloc`/`free` 的区别
- 指针运算、指针的指针、`void*`
- 栈上对象 vs 堆上对象的生命周期

**1.3 值语义 vs 引用语义**
- C++ 默认行为：赋值/传参/返回 都是拷贝
- 引用 `&`：别名，不拷贝
- 指针 vs 引用的选择场景
- `const` 三种位置：`const T*`、`T* const`、`const T&`

**1.4 RAII**
- 构造/析构函数，析构函数自动释放资源
- 为什么 C++ 不需要 `try-finally`
- 简单 RAII 示例：文件句柄包装、动态数组包装

### 练习
实现 `MathVector` 类：动态数组、构造/拷贝/赋值/析构（Rule of Three）、`operator[]`、`dot()`，与 numpy 结果对比。

---

## 阶段二：泛型与 STL

### 目标
学会用 STL 管理内存，专注算法逻辑而非资源管理。

### 知识点

**2.1 模板基础**
- 函数模板、类模板
- 模板实例化：编译器看到具体类型才生成代码
- 头文件必须包含模板实现

**2.2 STL 容器**
- `std::vector`：动态数组，默认容器
- `std::array`：编译期定长，栈上零开销
- `std::map` / `std::unordered_map`：红黑树 vs 哈希表
- `std::string`：真正的字符串对象
- 容器存对象 vs 存指针

**2.3 STL 算法与迭代器**
- 迭代器：指针的泛化，容器与算法的桥梁
- `<algorithm>`：`sort`、`find`、`transform`、`accumulate`
- lambda 表达式
- 范围 for

### 练习
1. 用 `std::vector` + `<algorithm>` 改写 MathVector，对比代码量
2. 实现 2D 网格 A* 路径搜索
3. 实现 2D KD-Tree，支持最近邻查询

---

## 阶段三：性能优化与 Python 互调

### 目标
让代码跑得更快，并与 Python 互操作。

### 知识点

**3.1 内存与缓存**
- CPU cache line（64 字节），缓存局部性
- AoS vs SoA 布局
- `std::vector` 连续内存优势 vs `std::list`

**3.2 移动语义**
- 左值/右值，`std::move` 本质是类型转换
- 移动构造/移动赋值（Rule of Five）
- RVO/NRVO 返回值优化
- `emplace_back` vs `push_back`

**3.3 Eigen 入门**
- 表达式模板：`a + b * c` 零临时矩阵
- 固定大小 vs 动态大小矩阵
- `Eigen::Map` 与 `std::vector` 互操作
- GP 核函数的 Eigen 实现

**3.4 pybind11 互调**
- C++ 函数暴露为 Python 模块
- `pybind11/eigen.h`：Eigen ↔ numpy 自动转换
- 在现有 GP baseline 中挑热点函数用 C++ 重写

### 练习
1. 用 Eigen 实现 RBF + Matern52 核函数，与 sklearn 对比输出
2. 用 pybind11 打包核函数为 Python 模块
3. 实现简版 GP 回归（纯 Eigen），验证与 sklearn 结果一致

---

## 技术约束

- 编译器：MSVC（Windows）或 MinGW GCC，阶段三需与 Python 环境兼容
- 构建系统：CMake（阶段一引入，贯穿始终）
- C++ 标准：C++17
- Eigen 版本：3.4+
- pybind11：通过 pip/vcpkg 安装

## 目录结构（建议）

```
cpp_try/
├── phase1_values_memory/
│   ├── 01_compile_link/
│   ├── 02_stack_heap/
│   ├── 03_value_reference/
│   ├── 04_raii/
│   └── exercise_mathvector/
├── phase2_templates_stl/
│   ├── 01_templates/
│   ├── 02_containers/
│   ├── 03_algorithms_iterators/
│   ├── exercise_astar/
│   └── exercise_kdtree/
├── phase3_perf_pybind/
│   ├── 01_memory_cache/
│   ├── 02_move_semantics/
│   ├── 03_eigen/
│   ├── 04_pybind11/
│   ├── exercise_kernels/
│   └── exercise_gp_regression/
├── CMakeLists.txt
└── README.md
```
