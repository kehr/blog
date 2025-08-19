---
title: 解决Tornado无法识别svg文件的问题
subtitle: 每一个web开发框架都有一些不怎么为人知的坑，让你如鲠在喉。
layout: post
comments: true
cover: "/assets/img/tornado.png"
categories: Tornado
tags: tornado  bug
date: '2018-07-09 16:30:00'
---

Tornado 使用 mimetypes 探测文件的 mime 类型。当遇到 svg 文件时则无法确定，返回 None。

以下是 Tornado 识别文件类型的处理函数：

```python 
def get_content_type(self):
    """Returns the ``Content-Type`` header to be used for this request.
 
    .. versionadded:: 3.1
    """
    mime_type, encoding = mimetypes.guess_type(self.absolute_path)
    return mime_type
```

` guess_type`：这个 guess 有点任性了~


修复代码：


```python 
class CustomStaticFileHandler(tornado.web.StaticFileHandler):
    """（Bug fixed）解决Tornado 默认无法识别 svg 文件的问题"""
    def get_content_type(self):
        mime_type = super(CustomStaticFileHandler, self).get_content_type()
        
        if self.absolute_path.endswith(".svg"):
            mime_type = "image/svg+xml"
        return mime_type
```

在设置 Application 时，指定处理静态文件的类：

```python 
"static_handler_class": CustomStaticFileHandler,
```

完成