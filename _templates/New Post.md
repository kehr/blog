<%*
const title = tp.file.title;
const date = tp.date.now("YYYY-MM-DD");
if (!title.match(/^\d{4}-\d{2}-\d{2}/)) {
  await tp.file.rename(`${date}-${title}`);
}
-%>
---
title: <% tp.file.title.replace(/^\d{4}-\d{2}-\d{2}-/, "") %>
description:
categories:
  - Older Posts
tags:
  - notes
image:
  path: /assets/img/default.jpg
date: <% tp.date.now("YYYY-MM-DD HH:mm") %>
---

> 

##