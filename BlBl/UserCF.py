"""
基于用户的协同过滤推荐算法（修复版）
修复了数据加载、字段映射和推荐生成的问题
"""
import csv
import random
import pymysql
import math
from operator import itemgetter
from datetime import datetime
import sys


class UserBasedCF():
    def __init__(self, n_sim_user=3, n_rec_video=5):
        self.n_sim_user = n_sim_user
        self.n_rec_video = n_rec_video
        self.trainSet = {}  # {user_id: {video_id: rating}}
        self.testSet = {}  # {user_id: {video_id: rating}}
        self.user_sim_matrix = {}  # {user_id: {other_user_id: similarity}}
        self.video_count = 0
        self.all_videos = set()
        print(f'相似用户数 = {self.n_sim_user}')
        print(f'推荐视频数 = {self.n_rec_video}')

    def get_dataset(self, filename, pivot=0.85):
        """从CSV文件加载数据集"""
        trainSet_len = 0
        testSet_len = 0

        for line in self.load_file(filename):
            try:
                parts = line.strip().split(',')
                if len(parts) != 3:
                    continue

                user, video, rating = parts
                user = str(user).strip()
                video = str(video).strip()

                if not user or not video:
                    continue

                self.all_videos.add(video)

                if random.random() < pivot:
                    self.trainSet.setdefault(user, {})
                    self.trainSet[user][video] = int(rating)
                    trainSet_len += 1
                else:
                    self.testSet.setdefault(user, {})
                    self.testSet[user][video] = int(rating)
                    testSet_len += 1
            except Exception as e:
                print(f"解析行时出错: {line}, 错误: {e}")
                continue

        print('训练集和测试集划分成功!')
        print(f'训练集大小 = {trainSet_len}, 用户数: {len(self.trainSet)}')
        print(f'测试集大小 = {testSet_len}, 用户数: {len(self.testSet)}')

        # 输出训练集中的所有用户
        train_users = list(self.trainSet.keys())
        print(f"训练集中的用户: {train_users}")

        # 特别检查用户25
        if '25' in self.trainSet:
            print(f"✓ 用户25在训练集中，浏览了 {len(self.trainSet['25'])} 个视频")
        else:
            print(f"✗ 用户25不在训练集中")

    def load_file(self, filename):
        """加载CSV文件"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i == 0:  # 跳过标题行
                        continue
                    yield line
            print(f'加载 {filename} 成功!')
        except Exception as e:
            print(f"加载文件 {filename} 时出错: {e}")

    def calc_user_sim(self):
        """计算用户相似度矩阵"""
        if not self.trainSet:
            print("训练集为空，无法计算相似度")
            return

        # 构建视频-用户倒排表
        video_user = {}
        print('构建视频-用户表...')

        for user, videos in self.trainSet.items():
            for video in videos:
                video_user.setdefault(video, set())
                video_user[video].add(user)

        self.video_count = len(video_user)
        print(f'视频总数 = {self.video_count}')

        if self.video_count == 0:
            print("没有找到共现视频")
            return

        # 构建用户共现矩阵
        print('构建用户共现矩阵...')
        for video, users in video_user.items():
            for u in users:
                for v in users:
                    if u == v:
                        continue
                    self.user_sim_matrix.setdefault(u, {})
                    self.user_sim_matrix[u].setdefault(v, 0)
                    self.user_sim_matrix[u][v] += 1

        print('计算用户相似度矩阵...')
        for u, related_users in self.user_sim_matrix.items():
            for v, count in related_users.items():
                if u in self.trainSet and v in self.trainSet:
                    u_videos = len(self.trainSet[u])
                    v_videos = len(self.trainSet[v])

                    if u_videos > 0 and v_videos > 0:
                        similarity = count / math.sqrt(u_videos * v_videos)
                        self.user_sim_matrix[u][v] = min(similarity, 1.0)

        print('计算用户相似度矩阵成功!')

        # 输出用户25的相似用户（如果存在）
        if '25' in self.user_sim_matrix:
            similar_to_25 = sorted(self.user_sim_matrix['25'].items(),
                                   key=itemgetter(1), reverse=True)[:5]
            if similar_to_25:
                print(f"用户25的相似用户(前5):")
                for other_user, sim in similar_to_25:
                    print(f"  用户{other_user}: 相似度 {sim:.4f}")
            else:
                print("用户25没有相似用户")

    def recommend(self, user):
        """为用户生成推荐"""
        K = self.n_sim_user
        N = self.n_rec_video

        # 检查用户是否在训练集中
        if user not in self.trainSet:
            return []

        watched_videos = set(self.trainSet[user].keys())

        # 如果用户没有相似用户，使用热门视频后备
        if user not in self.user_sim_matrix or not self.user_sim_matrix[user]:
            return self.get_popular_fallback(watched_videos, N)

        # 获取最相似的K个用户
        similar_users = sorted(self.user_sim_matrix[user].items(),
                               key=lambda x: x[1], reverse=True)

        # 如果相似用户少于K，使用所有可用相似用户
        actual_K = min(K, len(similar_users))
        similar_users = similar_users[:actual_K]

        rank = {}
        for other_user, similarity in similar_users:
            if similarity <= 0 or other_user not in self.trainSet:
                continue

            for video in self.trainSet[other_user]:
                if video in watched_videos:
                    continue

                rank.setdefault(video, 0.0)
                rank[video] += similarity

        if not rank:
            return self.get_popular_fallback(watched_videos, N)

        # 归一化得分到0-5分
        max_score = max(rank.values())
        if max_score > 0:
            for video in rank:
                rank[video] = (rank[video] / max_score) * 5.0

        # 返回前N个推荐
        return sorted(rank.items(), key=lambda x: x[1], reverse=True)[:N]

    def get_popular_fallback(self, watched_videos, N):
        """获取热门视频作为后备推荐"""
        if not self.trainSet:
            return []

        # 计算每个视频的观看次数
        video_popularity = {}
        for user_videos in self.trainSet.values():
            for video in user_videos:
                video_popularity[video] = video_popularity.get(video, 0) + 1

        # 过滤掉用户已观看的视频
        for video in watched_videos:
            video_popularity.pop(video, None)

        if not video_popularity:
            return []

        # 按流行度排序
        popular_videos = sorted(video_popularity.items(),
                                key=lambda x: x[1], reverse=True)[:N]

        # 转换为(视频ID, 评分)格式
        result = []
        if popular_videos:
            max_pop = max([count for _, count in popular_videos])
            for video, count in popular_videos:
                score = (count / max_pop) * 5.0 if max_pop > 0 else 3.0
                result.append((video, score))

        return result

    def evaluate_and_save(self):
        """评估并保存推荐结果到数据库"""
        print("开始生成推荐并保存到数据库...")

        if not self.trainSet:
            print("训练集为空，无法生成推荐")
            return

        try:
            # 连接数据库
            db = pymysql.connect(
                host="localhost",
                user='root',
                password='li974521',
                database='bill_video',
                charset='utf8'
            )
            cursor = db.cursor()

            # 清空推荐表
            cursor.execute("TRUNCATE TABLE myapp_rec;")
            db.commit()
            print("已清空推荐表")

            # 准备插入语句
            insert_sql = """
                INSERT INTO myapp_rec (user_id, video_id, score, created_at) 
                VALUES (%s, %s, %s, NOW())
            """

            all_recommendations = []

            # 为每个用户生成推荐
            for user_id in self.trainSet.keys():
                recommendations = self.recommend(user_id)

                for video_id, score in recommendations:
                    try:
                        # 确保数据类型正确
                        user_id_int = int(user_id)
                        video_id_int = int(video_id)
                        score_float = float(score)

                        all_recommendations.append((user_id_int, video_id_int, score_float))
                    except (ValueError, TypeError) as e:
                        print(f"数据类型转换错误: user={user_id}, video={video_id}, score={score}, 错误: {e}")
                        continue

            # 批量插入推荐数据
            if all_recommendations:
                try:
                    cursor.executemany(insert_sql, all_recommendations)
                    db.commit()
                    print(f"成功插入 {len(all_recommendations)} 条推荐记录")
                except Exception as e:
                    print(f"批量插入失败: {e}")
                    db.rollback()

            # 特别处理用户25
            cursor.execute("SELECT COUNT(*) FROM myapp_rec WHERE user_id = 25")
            count_25 = cursor.fetchone()[0]

            if count_25 == 0:
                print("为用户25生成后备推荐...")

                # 如果用户25在训练集中但没有推荐，使用热门视频
                if '25' in self.trainSet:
                    recommendations = self.recommend('25')

                    if recommendations:
                        for video_id, score in recommendations:
                            try:
                                video_id_int = int(video_id)
                                score_float = float(score)
                                cursor.execute(insert_sql, (25, video_id_int, score_float))
                            except Exception as e:
                                print(f"插入用户25推荐失败: {e}")
                                continue
                    else:
                        # 使用全局热门视频
                        popular_fallback = self.get_popular_fallback(set(), 5)
                        for video_id, score in popular_fallback:
                            try:
                                video_id_int = int(video_id)
                                score_float = float(score)
                                cursor.execute(insert_sql, (25, video_id_int, score_float))
                            except Exception as e:
                                print(f"插入用户25热门视频失败: {e}")
                                continue

                db.commit()
                print(f"已为用户25生成 {cursor.rowcount} 条推荐")

            # 统计信息
            cursor.execute("SELECT COUNT(*) FROM myapp_rec")
            total_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM myapp_rec")
            user_count = cursor.fetchone()[0]

            print(f"推荐表统计: 总记录数={total_count}, 唯一用户数={user_count}")

            cursor.close()
            db.close()

        except Exception as e:
            print(f"数据库操作失败: {e}")
            import traceback
            traceback.print_exc()


def create_rating_csv_from_db():
    """从数据库读取wishlist数据并创建rating.csv文件"""
    print("从数据库读取数据创建rating.csv...")

    try:
        # 连接数据库
        db = pymysql.connect(
            host='localhost',
            user='root',
            password='li974521',
            database='bill_video',
            charset='utf8'
        )
        cursor = db.cursor()

        # 查询wishlist表
        sql = "SELECT user_id, video_id FROM myapp_wishlist"
        cursor.execute(sql)
        data = cursor.fetchall()

        print(f"从myapp_wishlist获取到 {len(data)} 条数据")

        if data:
            # 统计用户25的记录
            user_25_count = 0
            for user_id, video_id in data:
                if user_id == 25:
                    user_25_count += 1

            print(f"用户25有 {user_25_count} 条浏览记录")

            # 显示前几条数据
            print("前5条数据样例:")
            for i, (user_id, video_id) in enumerate(data[:5]):
                print(f"  第{i + 1}条: 用户ID={user_id}, 视频ID={video_id}")

        # 写入CSV文件
        with open('rating.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'video_id', 'rating'])

            for user_id, video_id in data:
                writer.writerow([user_id, video_id, 1])  # 默认评分1

        print("数据已保存到 rating.csv")

        cursor.close()
        db.close()

        return len(data)

    except Exception as e:
        print(f"从数据库加载数据失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def test_recommendation():
    """测试推荐结果"""
    print("\n" + "=" * 50)
    print("测试推荐结果")
    print("=" * 50)

    try:
        db = pymysql.connect(
            host='localhost',
            user='root',
            password='li974521',
            database='bill_video',
            charset='utf8'
        )
        cursor = db.cursor()

        # 测试1: 检查用户25的推荐
        print("\n1. 检查用户25的推荐记录:")
        cursor.execute("""
            SELECT r.id, r.user_id, r.video_id, r.score, r.created_at, v.title
            FROM myapp_rec r
            LEFT JOIN myapp_studyclean v ON r.video_id = v.id
            WHERE r.user_id = 25
            ORDER BY r.score DESC
        """)

        recs_25 = cursor.fetchall()

        if recs_25:
            print(f"✓ 用户25有 {len(recs_25)} 条推荐:")
            for rec in recs_25:
                rec_id, user_id, video_id, score, created_at, title = rec
                print(f"   推荐ID: {rec_id}, 视频ID: {video_id}, 评分: {score:.4f}, 标题: {title or '未知'}")
        else:
            print("✗ 用户25没有推荐记录")

        # 测试2: 检查所有推荐
        print("\n2. 所有推荐记录统计:")
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT user_id) FROM myapp_rec")
        total, users = cursor.fetchone()
        print(f"   总推荐数: {total}, 涉及用户数: {users}")

        cursor.close()
        db.close()

    except Exception as e:
        print(f"测试推荐结果失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("协同过滤推荐算法（修复版）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 步骤1: 从数据库创建rating.csv
    data_count = create_rating_csv_from_db()

    if data_count == 0:
        print("错误: 没有从数据库读取到数据，请检查数据库连接和表结构")
        return

    # 步骤2: 创建推荐算法实例
    user_cf = UserBasedCF(n_sim_user=3, n_rec_video=5)

    # 步骤3: 加载数据集
    print("\n" + "-" * 40)
    print("加载数据集...")
    user_cf.get_dataset('rating.csv', pivot=0.9)  # 90%数据作为训练集

    # 步骤4: 计算用户相似度
    print("\n" + "-" * 40)
    print("计算用户相似度...")
    user_cf.calc_user_sim()

    # 步骤5: 生成并保存推荐
    print("\n" + "-" * 40)
    user_cf.evaluate_and_save()

    # 步骤6: 测试推荐结果
    test_recommendation()

    print("\n" + "=" * 60)
    print("算法运行完成!")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 最后提示
    print("\n提示: 算法运行完成后，请:")
    print("1. 刷新Django推荐页面 (/video_rec/)")
    print("2. 如果仍无推荐，请检查数据库myapp_rec表中是否有用户25的记录")
    print("3. 如有问题，请提供最新的运行日志")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback

        traceback.print_exc()
