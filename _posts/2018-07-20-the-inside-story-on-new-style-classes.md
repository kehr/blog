---
title: 有关Python新式类的前世今生
layout: post
comments: true
cover: "/assets/img/python-history.png"
categories: Python秘史
tags: Python  类
---

> 本文翻译自 [《The Inside Story on New-Style Classes》][1]。  
> Notice：1.  专有名词为避免歧义会保留原文。2. 关键内容译者会在原文基础上加上自己的理解。

表面上，新式类（new-style classes）和传统类（origin class）在实现上看起来非常像。然而，新式类却涵盖了一些新概念：

- low-level constructors（低级构造器） named `__new__()`
- descriptors, a generalized way to customize attribute access
- static methods（静态方法） and class methods（类方法）
- properties (computed attributes)
- decorators (introduced in Python 2.4)
- slots
- a new Method Resolution Order (MRO)

下面几部分，将分别介绍这些概念。

# 1. Low-level constructors and `__new__()`

传统意义上讲，类中定义的 `__init__` 方法决定了类在**创建之后**如何初始化。但在有些场景里，类的作者希望自定义实例的**创建过程**。例如，假设一个对象从持久化数据库（persistant database）中恢复，旧式类（old-style）不会提供定制创建对象的方法（hook），不过有一些模块却允许通过非标准的方式创建类（如，`new`模块）。

新式类拥有创建类的方法`__new__`，可以让类的作者定制如何创建类的实例对象。通过重写 `__new__()`，类作者可以实现类如`单例模式`的设计模式，返回一个之前已经创建的类实例，或者返回一个不同的类。然而`__new__`却有其它重要用途。例如，在`pickle`模块中，`__new__`被用来创建一个未实例化的对象。这个案例中，虽然实例被创建，但 `__init__` 方法并未被调用。


`__new__` 的另一个用途是帮助改进不可变类型的子类。根据其不变性的性质，这些类型的对象无法通过标准的`__init __`方法进行初始化。相反，任何特殊初始化方法必须和该对象创建时的行为保持一致；例如，如果类想要修改存储在不可变对象中的值，则`__new__`方法可以通过将修改后的值传递给基类`__new__`方法来完成。


未完待续...

[1]: http://python-history.blogspot.com/2010/06/inside-story-on-new-style-classes.html