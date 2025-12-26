"""
基于用户的协同过滤推荐算法（增强版）
修复了相似度计算、推荐逻辑和类别偏好问题
"""
import csv
import random
import pymysql
import math
from collections import defaultdict
from operator import itemgetter
from datetime import datetime
import numpy as np


class EnhancedUserBasedCF():
    def __init__(self, n_sim_user=5, n_rec_video=8, min_common=2):
        """
        初始化
        Args:
            n_sim_user: 相似用户数量
            n_rec_video: 推荐视频数量
            min_common: 最小共同观看数
        """
        self.n_sim_user = n_sim_user
        self.n_rec_video = n_rec_video
        self.min_common = min_common

        # 数据存储
        self.trainSet = {}  # {user_id: {video_id: rating}}
        self.testSet = {}   # {user_id: {video_id: rating}}

        # 相似度矩阵
        self.user_sim_matrix = {}  # {user_id: {other_user_id: similarity}}

        # 增强数据
        self.video_categories = {}  # {video_id: category}
        self.user_categories = {}  # {user_id: {category: weight}}

        # 统计信息
        self.user_mean_ratings = {}  # 用户平均评分
        self.all_videos = set()

        print(f'增强协同过滤推荐算法')
        print(f'相似用户数 = {self.n_sim_user}')
        print(f'推荐视频数 = {self.n_rec_video}')
        print(f'最小共同观看 = {self.min_common}')

    def load_video_categories(self, db_connection):
        """从数据库加载视频分类信息"""
        print("加载视频分类信息...")
        try:
            cursor = db_connection.cursor()

            # 查询视频分类
            query = """
            SELECT id, category, video_type 
            FROM study_clean 
            WHERE category IS NOT NULL
            """
            cursor.execute(query)

            for video_id, category, video_type in cursor.fetchall():
                # 创建复合分类
                if video_type and video_type.strip():
                    full_category = f"{category}_{video_type}"
                else:
                    full_category = category

                self.video_categories[str(video_id)] = full_category

            print(f"已加载 {len(self.video_categories)} 个视频的分类信息")
            cursor.close()

        except Exception as e:
            print(f"加载视频分类失败: {e}")
            import traceback
            traceback.print_exc()

    def get_dataset(self, filename, pivot=0.85):
        """从CSV文件加载数据集"""
        trainSet_len = 0
        testSet_len = 0
        user_counts = defaultdict(int)
        video_counts = defaultdict(int)

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
                user_counts[user] += 1
                video_counts[video] += 1

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

        # 计算用户平均评分
        for user, videos in self.trainSet.items():
            if videos:
                self.user_mean_ratings[user] = sum(videos.values()) / len(videos)

        # 分析用户行为
        self.analyze_user_behavior()

    def analyze_user_behavior(self):
        """分析用户行为特征"""
        print("\n=== 用户行为分析 ===")

        # 统计用户观看数量
        user_watch_counts = {}
        for user, videos in self.trainSet.items():
            user_watch_counts[user] = len(videos)

        # 输出活跃用户
        sorted_users = sorted(user_watch_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        print("活跃用户TOP 10:")
        for user, count in sorted_users:
            print(f"  用户{user}: {count} 个视频")

        # 特别检查用户25和27
        for user_id in ['25', '27']:
            if user_id in self.trainSet:
                videos = self.trainSet[user_id]
                print(f"\n用户{user_id}的观看行为:")
                print(f"  观看视频数: {len(videos)}")

                # 获取视频标题
                try:
                    db = pymysql.connect(
                        host="localhost",
                        user='root',
                        password='li974521',
                        database='bill_video',
                        charset='utf8'
                    )
                    cursor = db.cursor()

                    for video_id in list(videos.keys())[:5]:  # 只看前5个
                        query = "SELECT title, category FROM study_clean WHERE id = %s"
                        cursor.execute(query, (int(video_id),))
                        result = cursor.fetchone()
                        if result:
                            title, category = result
                            print(f"    视频{video_id}: {title} ({category})")

                    cursor.close()
                    db.close()
                except Exception as e:
                    print(f"    获取视频信息失败: {e}")

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

    def calc_user_sim_enhanced(self):
        """增强版用户相似度计算（考虑共同观看数量和评分）"""
        if not self.trainSet:
            print("训练集为空，无法计算相似度")
            return

        print("构建增强用户相似度矩阵...")

        # 构建视频-用户倒排表
        video_user = defaultdict(set)
        for user, videos in self.trainSet.items():
            for video in videos:
                video_user[video].add(user)

        # 构建用户相似度矩阵
        self.user_sim_matrix = {}

        # 计算用户对之间的相似度
        for video, users in video_user.items():
            user_list = list(users)
            for i in range(len(user_list)):
                for j in range(i + 1, len(user_list)):
                    u1, u2 = user_list[i], user_list[j]

                    # 初始化数据结构
                    if u1 not in self.user_sim_matrix:
                        self.user_sim_matrix[u1] = {}
                    if u2 not in self.user_sim_matrix:
                        self.user_sim_matrix[u2] = {}

                    # 增加共同观看计数
                    self.user_sim_matrix[u1].setdefault(u2, {"common": 0, "ratings": []})
                    self.user_sim_matrix[u2].setdefault(u1, {"common": 0, "ratings": []})

                    self.user_sim_matrix[u1][u2]["common"] += 1
                    self.user_sim_matrix[u2][u1]["common"] += 1

        print("计算皮尔逊相关系数...")
        # 计算最终相似度（皮尔逊相关系数）
        for u1 in self.user_sim_matrix:
            for u2 in self.user_sim_matrix[u1]:
                common_info = self.user_sim_matrix[u1][u2]

                if common_info["common"] >= self.min_common:
                    # 获取共同观看的视频
                    common_videos = set(self.trainSet.get(u1, {})).intersection(
                                    set(self.trainSet.get(u2, {})))

                    if len(common_videos) >= self.min_common:
                        # 收集评分
                        ratings_u1 = []
                        ratings_u2 = []

                        for video in common_videos:
                            rating1 = self.trainSet.get(u1, {}).get(video, 0)
                            rating2 = self.trainSet.get(u2, {}).get(video, 0)
                            ratings_u1.append(rating1)
                            ratings_u2.append(rating2)

                        # 计算皮尔逊相关系数
                        if len(ratings_u1) >= 2:
                            corr = self.pearson_sim(ratings_u1, ratings_u2)
                            # 共同观看数量作为权重
                            weighted_sim = corr * (1 + math.log1p(len(common_videos)))
                            self.user_sim_matrix[u1][u2] = max(0, weighted_sim)
                        else:
                            self.user_sim_matrix[u1][u2] = 0
                    else:
                        self.user_sim_matrix[u1][u2] = 0
                else:
                    self.user_sim_matrix[u1][u2] = 0

        print("相似度计算完成!")

        # 输出用户25和27的相似用户
        self.analyze_similar_users(['25', '27'])

    def pearson_sim(self, ratings1, ratings2):
        """计算皮尔逊相关系数"""
        n = len(ratings1)
        if n == 0:
            return 0

        sum1 = sum(ratings1)
        sum2 = sum(ratings2)
        sum1_sq = sum([r*r for r in ratings1])
        sum2_sq = sum([r*r for r in ratings2])
        p_sum = sum([ratings1[i] * ratings2[i] for i in range(n)])

        num = p_sum - (sum1 * sum2 / n)
        den = math.sqrt((sum1_sq - sum1*sum1/n) * (sum2_sq - sum2*sum2/n))

        if den == 0:
            return 0
        return num / den

    def analyze_similar_users(self, target_users):
        """分析目标用户的相似用户"""
        print("\n=== 相似用户分析 ===")

        for user in target_users:
            if user in self.user_sim_matrix:
                # 获取相似用户
                similar_users = []
                for other_user, sim in self.user_sim_matrix[user].items():
                    if isinstance(sim, (int, float)) and sim > 0:
                        # 获取共同观看数量
                        common_videos = set(self.trainSet.get(user, {})).intersection(
                                      set(self.trainSet.get(other_user, {})))

                        if len(common_videos) > 0:
                            similar_users.append((other_user, sim, len(common_videos)))

                # 按相似度排序
                similar_users.sort(key=lambda x: x[1], reverse=True)

                print(f"\n用户{user}的相似用户(前5):")
                for other_user, sim, common_count in similar_users[:5]:
                    # 获取用户类别偏好
                    user_pref = self.get_user_category_preference(user)
                    other_pref = self.get_user_category_preference(other_user)

                    print(f"  用户{other_user}: 相似度={sim:.3f}, 共同观看={common_count}")
                    print(f"    用户{user}偏好: {list(user_pref.items())[:3]}")
                    print(f"    用户{other_user}偏好: {list(other_pref.items())[:3]}")
            else:
                print(f"用户{user}没有相似用户")

    def get_user_category_preference(self, user_id):
        """获取用户类别偏好"""
        if not self.video_categories:
            return {}

        if user_id in self.trainSet:
            category_counts = defaultdict(int)
            videos = self.trainSet[user_id]

            for video in videos:
                if video in self.video_categories:
                    category = self.video_categories[video]
                    category_counts[category] += 1

            # 归一化
            total = sum(category_counts.values())
            if total > 0:
                return {cat: count/total for cat, count in category_counts.items()}

        return {}

    def recommend_enhanced(self, user):
        """增强版推荐算法"""
        K = self.n_sim_user
        N = self.n_rec_video

        # 检查用户是否在训练集中
        if user not in self.trainSet:
            print(f"用户{user}不在训练集中，使用热门推荐")
            return self.get_popular_fallback(set(), N)

        watched_videos = set(self.trainSet[user].keys())

        # 获取用户类别偏好
        user_preferences = self.get_user_category_preference(user)
        preferred_categories = set(user_preferences.keys())

        print(f"\n为用户{user}生成推荐:")
        print(f"  已观看视频数: {len(watched_videos)}")
        print(f"  类别偏好: {list(user_preferences.items())[:5]}")

        # 获取相似用户
        if user not in self.user_sim_matrix or not self.user_sim_matrix[user]:
            print("  没有找到相似用户，使用热门推荐")
            return self.get_popular_fallback(watched_videos, N)

        # 过滤相似用户（相似度>0）
        similar_users = []
        for other_user, sim in self.user_sim_matrix[user].items():
            if isinstance(sim, (int, float)) and sim > 0:
                # 检查是否有足够的共同观看
                common_videos = set(self.trainSet.get(user, {})).intersection(
                              set(self.trainSet.get(other_user, {})))
                if len(common_videos) >= 1:  # 至少有1个共同观看
                    similar_users.append((other_user, sim))

        if not similar_users:
            print("  没有符合条件的相似用户，使用热门推荐")
            return self.get_popular_fallback(watched_videos, N)

        # 按相似度排序
        similar_users.sort(key=lambda x: x[1], reverse=True)
        print(f"  找到 {len(similar_users)} 个相似用户")

        # 取前K个相似用户
        top_similar_users = similar_users[:K]

        # 收集候选视频
        candidate_videos = defaultdict(float)

        for other_user, similarity in top_similar_users:
            other_videos = self.trainSet.get(other_user, {})
            other_pref = self.get_user_category_preference(other_user)

            for video, rating in other_videos.items():
                if video in watched_videos:
                    continue

                # 计算视频与用户偏好的匹配度
                category_match = 1.0
                if self.video_categories and video in self.video_categories:
                    video_category = self.video_categories[video]
                    if video_category in preferred_categories:
                        category_match = 2.0  # 偏好类别权重更高
                    elif video_category in other_pref:
                        category_match = 1.5  # 相似用户偏好类别

                # 计算得分
                base_score = similarity * rating
                candidate_videos[video] += base_score * category_match

        if not candidate_videos:
            print("  没有候选视频，使用热门推荐")
            return self.get_popular_fallback(watched_videos, N)

        # 归一化得分
        max_score = max(candidate_videos.values())
        if max_score > 0:
            for video in candidate_videos:
                candidate_videos[video] = (candidate_videos[video] / max_score) * 5.0

        # 按得分排序
        ranked_videos = sorted(candidate_videos.items(),
                              key=lambda x: x[1], reverse=True)

        # 取前N个
        recommendations = ranked_videos[:N]

        # 输出推荐结果详情
        print(f"  生成 {len(recommendations)} 个推荐:")
        for video, score in recommendations[:5]:  # 只显示前5个
            category = self.video_categories.get(video, "未知")
            print(f"    视频{video}: 得分={score:.3f}, 类别={category}")

        return recommendations

    def get_popular_fallback(self, watched_videos, N):
        """获取热门视频作为后备推荐"""
        if not self.trainSet:
            return []

        # 计算视频流行度
        video_popularity = defaultdict(int)
        for user_videos in self.trainSet.values():
            for video in user_videos:
                video_popularity[video] += 1

        # 过滤已观看视频
        for video in watched_videos:
            video_popularity.pop(video, None)

        if not video_popularity:
            return []

        # 按流行度排序
        popular_videos = sorted(video_popularity.items(),
                               key=lambda x: x[1], reverse=True)

        # 转换为(视频ID, 评分)格式
        result = []
        if popular_videos:
            max_pop = max([count for _, count in popular_videos])
            for video, count in popular_videos[:N]:
                score = (count / max_pop) * 5.0 if max_pop > 0 else 3.0
                result.append((video, score))

        return result

    def save_recommendations(self):
        """保存推荐结果到数据库"""
        print("\n" + "="*50)
        print("保存推荐结果到数据库")
        print("="*50)

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

            # 加载视频分类信息
            self.load_video_categories(db)

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
            user_recommendation_stats = {}

            # 为每个用户生成推荐
            for user_id in self.trainSet.keys():
                recommendations = self.recommend_enhanced(user_id)

                user_recommendation_stats[user_id] = len(recommendations)

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
                    print(f"\n成功插入 {len(all_recommendations)} 条推荐记录")
                except Exception as e:
                    print(f"批量插入失败: {e}")
                    db.rollback()

            # 统计信息
            print("\n推荐统计:")
            for user_id, count in sorted(user_recommendation_stats.items(),
                                        key=lambda x: int(x[0])):
                if int(user_id) in [25, 27]:  # 特别关注25和27
                    print(f"  用户{user_id}: {count} 条推荐")

            # 查询数据库确认
            cursor.execute("SELECT COUNT(*) FROM myapp_rec")
            total_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM myapp_rec")
            user_count = cursor.fetchone()[0]

            print(f"\n数据库统计:")
            print(f"  总记录数: {total_count}")
            print(f"  唯一用户数: {user_count}")

            cursor.close()
            db.close()

        except Exception as e:
            print(f"数据库操作失败: {e}")
            import traceback
            traceback.print_exc()

    def verify_recommendations(self):
        """验证推荐结果"""
        print("\n" + "="*50)
        print("验证推荐结果")
        print("="*50)

        try:
            db = pymysql.connect(
                host='localhost',
                user='root',
                password='li974521',
                database='bill_video',
                charset='utf8'
            )
            cursor = db.cursor()

            # 检查用户25的推荐
            print("\n1. 用户25的推荐详情:")
            cursor.execute("""
                SELECT r.id, r.user_id, r.video_id, r.score, v.title, v.category
                FROM myapp_rec r
                LEFT JOIN study_clean v ON r.video_id = v.id
                WHERE r.user_id = 25
                ORDER BY r.score DESC
            """)

            recs_25 = cursor.fetchall()

            if recs_25:
                print(f"✓ 用户25有 {len(recs_25)} 条推荐:")
                python_count = 0
                anime_count = 0

                for rec in recs_25:
                    rec_id, user_id, video_id, score, title, category = rec
                    category_str = category if category else "未知"

                    if "Python" in str(title) or "python" in str(title).lower():
                        python_count += 1
                        print(f"  ✓ Python相关: 视频{video_id}, 评分{score:.2f}, 类别: {category_str}")
                    elif "二次元" in str(title) or "动漫" in str(title):
                        anime_count += 1
                        print(f"  ✗ 二次元: 视频{video_id}, 评分{score:.2f}, 类别: {category_str}")
                    else:
                        print(f"  - 其他: 视频{video_id}, 评分{score:.2f}, 类别: {category_str}")

                print(f"\n用户25推荐统计:")
                print(f"  Python相关: {python_count} 个")
                print(f"  二次元: {anime_count} 个")
                print(f"  其他: {len(recs_25) - python_count - anime_count} 个")
            else:
                print("✗ 用户25没有推荐记录")

            # 检查用户27的推荐
            print("\n2. 用户27的推荐详情:")
            cursor.execute("""
                SELECT r.id, r.user_id, r.video_id, r.score, v.title, v.category
                FROM myapp_rec r
                LEFT JOIN study_clean v ON r.video_id = v.id
                WHERE r.user_id = 27
                ORDER BY r.score DESC
            """)

            recs_27 = cursor.fetchall()

            if recs_27:
                print(f"✓ 用户27有 {len(recs_27)} 条推荐:")
                python_count = 0
                anime_count = 0

                for rec in recs_27:
                    rec_id, user_id, video_id, score, title, category = rec
                    category_str = category if category else "未知"

                    if "Python" in str(title) or "python" in str(title).lower():
                        python_count += 1
                        print(f"  ✗ Python相关: 视频{video_id}, 评分{score:.2f}, 类别: {category_str}")
                    elif "二次元" in str(title) or "动漫" in str(title):
                        anime_count += 1
                        print(f"  ✓ 二次元: 视频{video_id}, 评分{score:.2f}, 类别: {category_str}")
                    else:
                        print(f"  - 其他: 视频{video_id}, 评分{score:.2f}, 类别: {category_str}")

                print(f"\n用户27推荐统计:")
                print(f"  Python相关: {python_count} 个")
                print(f"  二次元: {anime_count} 个")
                print(f"  其他: {len(recs_27) - python_count - anime_count} 个")
            else:
                print("✗ 用户27没有推荐记录")

            # 总体统计
            print("\n3. 总体统计:")
            cursor.execute("""
                SELECT r.user_id, COUNT(*) as rec_count, 
                       GROUP_CONCAT(DISTINCT v.category) as categories
                FROM myapp_rec r
                LEFT JOIN study_clean v ON r.video_id = v.id
                GROUP BY r.user_id
                HAVING r.user_id IN (25, 27)
                ORDER BY r.user_id
            """)

            stats = cursor.fetchall()
            for user_id, rec_count, categories in stats:
                print(f"  用户{user_id}: {rec_count} 条推荐, 类别分布: {categories}")

            cursor.close()
            db.close()

        except Exception as e:
            print(f"验证推荐结果失败: {e}")
            import traceback
            traceback.print_exc()


def create_rating_csv_from_db():
    """从数据库读取wishlist数据并创建rating.csv文件"""
    print("从数据库读取数据创建rating.csv...")

    try:
        db = pymysql.connect(
            host='localhost',
            user='root',
            password='li974521',
            database='bill_video',
            charset='utf8'
        )
        cursor = db.cursor()

        # 查询wishlist表
        sql = """
        SELECT w.user_id, w.video_id, 5 as rating
        FROM myapp_wishlist w
        WHERE w.user_id IS NOT NULL AND w.video_id IS NOT NULL
        UNION
        SELECT v.user_id, v.video_id, 3 as rating
        FROM myapp_wishlist v
        WHERE v.user_id IS NOT NULL AND v.video_id IS NOT NULL
        """
        cursor.execute(sql)
        data = cursor.fetchall()

        print(f"获取到 {len(data)} 条交互数据")

        if data:
            # 统计用户25和27的记录
            for user_id in [25, 27]:
                user_count = sum(1 for uid, _, _ in data if uid == user_id)
                print(f"用户{user_id}有 {user_count} 条记录")

            # 显示前几条数据
            print("前5条数据样例:")
            for i, (user_id, video_id, rating) in enumerate(data[:5]):
                print(f"  第{i+1}条: 用户ID={user_id}, 视频ID={video_id}, 评分={rating}")

        # 写入CSV文件
        with open('rating.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'video_id', 'rating'])

            for user_id, video_id, rating in data:
                writer.writerow([user_id, video_id, rating])

        print("数据已保存到 rating.csv")

        cursor.close()
        db.close()

        return len(data)

    except Exception as e:
        print(f"从数据库加载数据失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """主函数"""
    print("=" * 60)
    print("增强协同过滤推荐算法")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 步骤1: 从数据库创建rating.csv
    data_count = create_rating_csv_from_db()

    if data_count == 0:
        print("错误: 没有从数据库读取到数据，请检查数据库连接和表结构")
        return

    # 步骤2: 创建推荐算法实例
    user_cf = EnhancedUserBasedCF(
        n_sim_user=5,  # 增加相似用户数
        n_rec_video=8,  # 增加推荐视频数
        min_common=2    # 最小共同观看数
    )

    # 步骤3: 加载数据集
    print("\n" + "-" * 40)
    print("加载数据集...")
    user_cf.get_dataset('rating.csv', pivot=0.8)  # 80%数据作为训练集

    # 步骤4: 计算用户相似度
    print("\n" + "-" * 40)
    print("计算用户相似度...")
    user_cf.calc_user_sim_enhanced()

    # 步骤5: 生成并保存推荐
    print("\n" + "-" * 40)
    user_cf.save_recommendations()

    # 步骤6: 验证推荐结果
    user_cf.verify_recommendations()

    print("\n" + "=" * 60)
    print("算法运行完成!")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 最后提示
    print("\n提示: 算法运行完成后，请:")
    print("1. 刷新Django推荐页面 (/video_rec/)")
    print("2. 检查myapp_rec表中的推荐结果")
    print("3. 如需调试，可以查看输出的详细日志")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()