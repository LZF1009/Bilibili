import pandas as pd
import pymysql

# 1. 读取CSV文件（指定正确的编码，避免中文乱码）
csv_file_path = 'clean3.csv'
# 读取时跳过可能的空行，确保列名正确
data = pd.read_csv(csv_file_path, encoding='utf-8-sig').dropna(how='all')

# 2. 查看并确认CSV实际列名（可选，用于调试）
print("CSV文件实际列名：")
for i, col in enumerate(data.columns):
    print(f"{i+1}. {col}")

# 3. 清洗标题（去除可能残留的HTML标签）
def clean_title(title):
    if isinstance(title, str):
        return title.replace('<em class="keyword">', '').replace('</em>', '').replace('&amp;', '&')
    return title
data['标题'] = data['标题'].apply(clean_title)

# 4. 转换发布时间格式（适配数据库datetime类型，处理可能的时间戳或字符串）
# 从CSV看“发布时间戳”是字符串格式（如2024-07-09 12:00:00），直接格式化即可
data['发布时间戳'] = pd.to_datetime(data['发布时间戳'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
# 删除时间转换失败的行（避免插入空值）
data = data.dropna(subset=['发布时间戳'])

# 5. 数据库连接配置（替换为你的实际密码）
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'li974521',  # 必须替换为你的真实MySQL密码
    'database': 'bill_video',    # 目标数据库名（已创建）
    'charset': 'utf8mb4',
    'connect_timeout': 10        # 连接超时时间，避免卡住
}

# 6. 连接数据库并执行数据插入
connection = None
try:
    # 建立数据库连接
    connection = pymysql.connect(**db_config)
    cursor = connection.cursor()
    print("\n数据库连接成功！开始插入数据...")

    # 定义插入SQL（字段与study_clean表、CSV列名严格对应）
    insert_sql = """
    INSERT INTO study_clean (
        video_id,        -- 视频ID（对应CSV“视频ID”）
        video_url,       -- 视频地址（对应CSV“视频地址”）
        author,          -- 作者（对应CSV“作者”）
        video_description, -- 视频文案（对应CSV“视频文案”）
        video_duration,  -- 视频时长（对应CSV“视频时长(分钟)”）
        damaku_count,    -- 弹幕数量（对应CSV“弹幕数量”）
        favorites_count, -- 收藏人数（对应CSV“收藏人数”）
        likes_count,     -- 点赞人数（对应CSV“点赞人数”）
        image_url,       -- 图片地址（对应CSV“图片地址”）
        publish_timestamp, -- 发布时间（对应CSV“发布时间戳”）
        comments_count,  -- 评论人数（对应CSV“评论人数”）
        tags,            -- 标签（对应CSV“标签”）
        title,           -- 标题（对应CSV“标题”）
        video_type,      -- 视频类型（对应CSV“视频类型”）
        category         -- 类别（对应CSV“类别”）
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # 逐行插入数据（批量插入更高效，这里用循环确保兼容性）
    insert_count = 0
    for _, row in data.iterrows():
        # 构造插入值（顺序与SQL字段完全一致，处理可能的空值）
        values = (
            row['视频ID'] if pd.notna(row['视频ID']) else '',
            row['视频地址'] if pd.notna(row['视频地址']) else '',
            row['作者'] if pd.notna(row['作者']) else '',
            row['视频文案'] if pd.notna(row['视频文案']) else '',
            row['视频时长(分钟)'] if pd.notna(row['视频时长(分钟)']) else '',
            int(row['弹幕数量']) if pd.notna(row['弹幕数量']) else 0,
            int(row['收藏人数']) if pd.notna(row['收藏人数']) else 0,
            int(row['点赞人数']) if pd.notna(row['点赞人数']) else 0,
            row['图片地址'] if pd.notna(row['图片地址']) else '',
            row['发布时间戳'] if pd.notna(row['发布时间戳']) else '1970-01-01 00:00:00',
            int(row['评论人数']) if pd.notna(row['评论人数']) else 0,
            row['标签'] if pd.notna(row['标签']) else '',
            row['标题'] if pd.notna(row['标题']) else '',
            row['视频类型'] if pd.notna(row['视频类型']) else '',
            row['类别'] if pd.notna(row['类别']) else ''
        )
        cursor.execute(insert_sql, values)
        insert_count += 1

    # 提交事务（必须执行，否则数据不会写入数据库）
    connection.commit()
    print(f"\n数据插入完成！共成功插入 {insert_count} 条数据到 study_clean 表。")

except pymysql.OperationalError as e:
    print(f"\n数据库连接失败：{e}")
    print("请检查：1. MySQL服务是否已启动；2. 用户名/密码是否正确；3. 数据库bill_video是否存在。")
except Exception as e:
    # 出错时回滚事务，避免脏数据
    if connection:
        connection.rollback()
    print(f"\n插入数据失败：{e}")
finally:
    # 关闭游标和连接，释放资源
    if connection:
        cursor.close()
        connection.close()
        print("\n数据库连接已关闭。")