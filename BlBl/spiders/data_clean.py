import pandas as pd

# 读取CSV文件并指定列名
df = pd.read_csv(
    "data3.csv",
    names=[
        "视频ID", "视频地址", "作者", "视频文案", "视频时长(分钟)",
        "弹幕数量", "收藏人数", "点赞人数", "图片地址", "发布时间戳",
        "评论人数", "标签", "标题", "视频类型", "类别"
    ]
)

# 删除第一行（原表头）
df = df.drop(index=1)

# 替换标题、标签中的逗号（避免CSV格式混乱）
df["视频文案"] = df["视频文案"].replace(',', '，', regex=True)
df["标签"] = df["标签"].replace(',', '，', regex=True)
df["标题"] = df["标题"].replace(',', '，', regex=True)

# 保存清洗后的数据到新CSV文件
df.to_csv("clean3.csv", index=False)