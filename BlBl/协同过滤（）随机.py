"""
视频推荐生成脚本 - 修复语法错误版
功能：直接为用户25生成推荐数据，确保推荐页面有内容显示
"""
import pymysql
import sys
from datetime import datetime

def generate_recommendations():
    """生成推荐数据的主函数"""
    print("=" * 60)
    print("视频推荐生成器 v2.0")
    print("=" * 60)

    try:
        # 1. 连接数据库
        db = pymysql.connect(
            host="localhost",
            user="root",
            password="li974521",
            database="bill_video",
            charset="utf8"
        )
        cursor = db.cursor()

        # 2. 检查数据表
        print("检查数据表...")
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        print(f"数据库中的表: {tables}")

        # 3. 检查是否有myapp_studyclean表
        if 'study_clean' not in tables:
            print("错误: 没有找到study_clean表!")
            cursor.close()
            db.close()
            return False

        # 4. 检查视频数量
        cursor.execute("SELECT COUNT(*) FROM study_clean")
        video_count = cursor.fetchone()[0]

        if video_count == 0:
            print("警告: 视频表为空，添加示例视频...")
            add_sample_videos(cursor, db)
            cursor.execute("SELECT COUNT(*) FROM study_clean")
            video_count = cursor.fetchone()[0]

        print(f"视频表中有 {video_count} 个视频")

        # 5. 清空之前的推荐
        print("\n清空旧推荐...")
        if 'myapp_rec' in tables:
            cursor.execute("TRUNCATE TABLE myapp_rec")
            db.commit()
            print("已清空推荐表")
        else:
            print("推荐表不存在，将自动创建...")

        # 6. 为用户25生成推荐
        print("\n为用户25生成推荐...")

        # 获取5个随机视频作为推荐
        cursor.execute("""
            SELECT id, title FROM study_clean 
            ORDER BY RAND() 
            LIMIT 5
        """)

        recommended_videos = cursor.fetchall()

        if not recommended_videos:
            print("错误: 没有找到可推荐的视频!")
            cursor.close()
            db.close()
            return False

        print(f"找到 {len(recommended_videos)} 个推荐视频")

        # 7. 插入推荐数据
        insert_sql = """
            INSERT INTO myapp_rec (user_id, video_id, score, created_at) 
            VALUES (%s, %s, %s, NOW())
        """

        recommendations = []
        for i, (video_id, title) in enumerate(recommended_videos):
            # 评分从5.0递减
            score = 5.0 - (i * 0.5)
            recommendations.append((25, video_id, score))
            print(f"  视频ID: {video_id}, 标题: {title[:20] if title else '无标题'}, 评分: {score:.1f}")

        cursor.executemany(insert_sql, recommendations)
        db.commit()

        # 8. 验证插入结果
        cursor.execute("""
            SELECT r.id, r.video_id, r.score, v.title, r.created_at
            FROM myapp_rec r 
            LEFT JOIN study_clean v ON r.video_id = v.id 
            WHERE r.user_id = 25
            ORDER BY r.score DESC
        """)

        results = cursor.fetchall()
        print(f"\n✓ 成功为用户25生成了 {len(results)} 条推荐:")

        for rec_id, video_id, score, title, created_at in results:
            created_str = created_at.strftime('%Y-%m-%d %H:%M') if created_at else '未知时间'
            print(f"  ID:{rec_id:3d} 视频:{video_id:3d} 评分:{score:4.1f} 时间:{created_str} 标题:{title}")

        # 9. 统计数据
        cursor.execute("SELECT COUNT(*) FROM myapp_rec")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM myapp_rec")
        user_count = cursor.fetchone()[0]

        print(f"\n推荐表统计: 总记录数={total}, 涉及用户数={user_count}")

        cursor.close()
        db.close()

        print("\n" + "=" * 60)
        print("✅ 推荐生成成功!")
        print("请刷新推荐页面查看结果")
        print("=" * 60)

        return True

    except pymysql.Error as e:
        print(f"❌ 数据库错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 程序错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_sample_videos(cursor, db):
    """添加示例视频数据"""
    videos = [
        ("Python编程入门教程", "https://img.example.com/python.jpg", "编程", "2025-01-01 10:00:00"),
        ("Django框架实战项目", "https://img.example.com/django.jpg", "Web开发", "2025-01-02 11:00:00"),
        ("机器学习基础教程", "https://img.example.com/ml.jpg", "人工智能", "2025-01-03 12:00:00"),
        ("数据分析与可视化", "https://img.example.com/data.jpg", "数据分析", "2025-01-04 13:00:00"),
        ("前端开发全栈指南", "https://img.example.com/web.jpg", "前端", "2025-01-05 14:00:00"),
        ("后端架构设计原理", "https://img.example.com/backend.jpg", "后端", "2025-01-06 15:00:00"),
        ("算法与数据结构", "https://img.example.com/algo.jpg", "算法", "2025-01-07 16:00:00"),
        ("数据库优化技巧", "https://img.example.com/db.jpg", "数据库", "2025-01-08 17:00:00"),
        ("Linux系统管理", "https://img.example.com/linux.jpg", "操作系统", "2025-01-09 18:00:00"),
        ("网络安全基础", "https://img.example.com/security.jpg", "安全", "2025-01-10 19:00:00"),
    ]

    insert_sql = """
        INSERT INTO study_clean (title, image_url, category, publish_timestamp) 
        VALUES (%s, %s, %s, %s)
    """

    cursor.executemany(insert_sql, videos)
    db.commit()
    print(f"已添加 {len(videos)} 个示例视频")

def test_database_connection():
    """测试数据库连接"""
    print("测试数据库连接...")
    try:
        db = pymysql.connect(
            host="localhost",
            user="root",
            password="li974521",
            database="bill_video",
            charset="utf8"
        )
        cursor = db.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        db.close()
        print("✅ 数据库连接成功")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

def main():
    """主函数"""
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 测试数据库连接
    if not test_database_connection():
        print("请检查数据库配置:")
        print("  主机: localhost")
        print("  用户: root")
        print("  密码: li974521")
        print("  数据库: bill_video")
        return

    # 生成推荐
    success = generate_recommendations()

    if success:
        print("\n下一步操作:")
        print("1. 确保Django服务器正在运行: python manage.py runserver")
        print("2. 使用用户ID 25登录系统")
        print("3. 访问: http://localhost:8000/video_rec/")
        print("4. 如果仍不显示，请检查Django控制台输出")
    else:
        print("\n❌ 推荐生成失败，请检查以上错误信息")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
