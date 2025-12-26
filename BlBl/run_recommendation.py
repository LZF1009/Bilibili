"""
基于用户的协同过滤推荐算法（修正版）
修复了无相似用户时的问题
"""
import csv
import random
import pymysql
import math
from collections import defaultdict
from operator import itemgetter
from datetime import datetime


class UserBasedCF():
    def __init__(self, n_sim_user=0, n_rec_video=9):
        self.n_sim_user = n_sim_user
        self.n_rec_video = n_rec_video

        # 数据存储
        self.trainSet = {}  # {user_id: {video_id: rating}}
        self.testSet = {}   # {user_id: {video_id: rating}}
        self.user_sim_matrix = {}  # {user_id: {other_user_id: similarity}}

        # 新增：视频标签/分类信息
        self.video_tags = {}  # {video_id: {tag: weight}}
        self.user_profiles = {}  # {user_id: {tag: weight}}

        print(f'相似用户数 = {self.n_sim_user}')
        print(f'推荐视频数 = {self.n_rec_video}')

    def load_video_tags(self, db_connection):
        """加载视频标签信息"""
        print("加载视频标签信息...")
        try:
            cursor = db_connection.cursor()

            # 查询视频分类和标签
            query = """
            SELECT id, category, video_type, title 
            FROM study_clean 
            WHERE category IS NOT NULL
            """
            cursor.execute(query)

            for video_id, category, video_type, title in cursor.fetchall():
                video_id = str(video_id)
                self.video_tags[video_id] = {}

                # 添加类别作为标签
                if category:
                    # 将类别转换为多个标签
                    categories = str(category).split('/')
                    for cat in categories:
                        cat = cat.strip()
                        if cat:
                            self.video_tags[video_id][cat] = 1.0

                # 添加子类别作为标签
                if video_type:
                    subcategories = str(video_type).split('/')
                    for subcat in subcategories:
                        subcat = subcat.strip()
                        if subcat:
                            self.video_tags[video_id][subcat] = 0.8

                # 从标题中提取关键词
                if title:
                    title = str(title).lower()
                    # 检查是否是Python相关
                    if 'python' in title or 'pandas' in title or 'numpy' in title:
                        self.video_tags[video_id]['python'] = 1.0
                        self.video_tags[video_id]['编程'] = 0.8
                    # 检查是否是二次元相关
                    elif '二次元' in title or '动漫' in title or '漫展' in title or 'cos' in title:
                        self.video_tags[video_id]['二次元'] = 1.0
                        self.video_tags[video_id]['动漫'] = 0.8

            print(f"已加载 {len(self.video_tags)} 个视频的标签信息")
            cursor.close()

        except Exception as e:
            print(f"加载视频标签失败: {e}")
            import traceback
            traceback.print_exc()

    def build_user_profiles(self):
        """构建用户兴趣画像"""
        print("构建用户兴趣画像...")
        for user_id, videos in self.trainSet.items():
            user_profile = defaultdict(float)

            for video_id, rating in videos.items():
                if video_id in self.video_tags:
                    for tag, weight in self.video_tags[video_id].items():
                        # 用户兴趣 = 标签权重 * 评分
                        user_profile[tag] += weight * rating

            # 归一化
            if user_profile:
                max_weight = max(user_profile.values())
                for tag in user_profile:
                    user_profile[tag] /= max_weight

            self.user_profiles[user_id] = user_profile

            # 显示用户兴趣
            if user_id in ['25', '27']:
                print(f"\n用户{user_id}的兴趣标签:")
                sorted_tags = sorted(user_profile.items(), key=lambda x: x[1], reverse=True)[:5]
                for tag, weight in sorted_tags:
                    print(f"  {tag}: {weight:.3f}")

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

    def calc_user_sim_with_content(self):
        """计算用户相似度（结合内容）"""
        if not self.trainSet:
            print("训练集为空，无法计算相似度")
            return

        print("计算用户相似度（结合行为相似度和内容相似度）...")

        # 1. 基于行为的相似度
        print("计算行为相似度...")
        behavior_sim = self._calc_behavior_similarity()

        # 2. 基于内容的相似度
        print("计算内容相似度...")
        content_sim = self._calc_content_similarity()

        # 3. 合并相似度
        print("合并相似度...")
        for user1 in self.trainSet:
            self.user_sim_matrix[user1] = {}

            for user2 in self.trainSet:
                if user1 == user2:
                    continue

                # 计算加权相似度
                w1 = 0.7  # 行为相似度权重
                w2 = 0.3  # 内容相似度权重

                sim1 = behavior_sim.get(user1, {}).get(user2, 0)
                sim2 = content_sim.get(user1, {}).get(user2, 0)

                total_sim = w1 * sim1 + w2 * sim2
                if total_sim > 0:
                    self.user_sim_matrix[user1][user2] = total_sim

        print("相似度计算完成!")

        # 输出用户25和27的相似用户
        self._print_similar_users(['25', '27'])

    def _calc_behavior_similarity(self):
        """计算基于行为的相似度（共同观看）"""
        behavior_sim = {}

        # 构建视频-用户倒排表
        video_user = {}
        for user, videos in self.trainSet.items():
            for video in videos:
                video_user.setdefault(video, set())
                video_user[video].add(user)

        # 计算用户对之间的共同观看
        for user1 in self.trainSet:
            behavior_sim[user1] = {}

            for user2 in self.trainSet:
                if user1 == user2:
                    continue

                # 计算共同观看的视频
                videos1 = set(self.trainSet[user1].keys())
                videos2 = set(self.trainSet[user2].keys())
                common_videos = videos1.intersection(videos2)

                if common_videos:
                    # 使用Jaccard相似度
                    union_videos = videos1.union(videos2)
                    sim = len(common_videos) / len(union_videos) if union_videos else 0
                    behavior_sim[user1][user2] = sim
                else:
                    behavior_sim[user1][user2] = 0

        return behavior_sim

    def _calc_content_similarity(self):
        """计算基于内容的相似度（兴趣标签）"""
        content_sim = {}

        for user1 in self.trainSet:
            content_sim[user1] = {}

            for user2 in self.trainSet:
                if user1 == user2:
                    continue

                # 获取用户兴趣向量
                profile1 = self.user_profiles.get(user1, {})
                profile2 = self.user_profiles.get(user2, {})

                if not profile1 or not profile2:
                    content_sim[user1][user2] = 0
                    continue

                # 计算余弦相似度
                common_tags = set(profile1.keys()).intersection(set(profile2.keys()))

                if not common_tags:
                    content_sim[user1][user2] = 0
                    continue

                dot_product = sum(profile1[tag] * profile2[tag] for tag in common_tags)
                norm1 = math.sqrt(sum(w * w for w in profile1.values()))
                norm2 = math.sqrt(sum(w * w for w in profile2.values()))

                if norm1 * norm2 > 0:
                    sim = dot_product / (norm1 * norm2)
                    content_sim[user1][user2] = sim
                else:
                    content_sim[user1][user2] = 0

        return content_sim

    def _print_similar_users(self, target_users):
        """输出目标用户的相似用户"""
        print("\n=== 用户相似度分析 ===")

        for user in target_users:
            if user in self.user_sim_matrix:
                similar_users = sorted(self.user_sim_matrix[user].items(),
                                     key=lambda x: x[1], reverse=True)[:5]

                if similar_users:
                    print(f"\n用户{user}的最相似用户:")
                    for other_user, sim in similar_users:
                        if sim > 0:
                            # 获取共同兴趣
                            common_interests = self._get_common_interests(user, other_user)
                            print(f"  用户{other_user}: 相似度={sim:.3f}")
                            if common_interests:
                                print(f"    共同兴趣: {common_interests}")
                else:
                    print(f"\n用户{user}: 没有找到相似用户（相似度为0）")
            else:
                print(f"\n用户{user}: 不在相似度矩阵中")

    def _get_common_interests(self, user1, user2):
        """获取两个用户的共同兴趣"""
        profile1 = self.user_profiles.get(user1, {})
        profile2 = self.user_profiles.get(user2, {})

        if not profile1 or not profile2:
            return []

        # 获取前5个兴趣标签
        interests1 = sorted(profile1.items(), key=lambda x: x[1], reverse=True)[:5]
        interests2 = sorted(profile2.items(), key=lambda x: x[1], reverse=True)[:5]

        # 找出共同的兴趣
        tags1 = {tag for tag, _ in interests1}
        tags2 = {tag for tag, _ in interests2}
        common_tags = tags1.intersection(tags2)

        return list(common_tags)

    def recommend_for_user(self, user):
        """为用户生成推荐（混合方法）"""
        K = self.n_sim_user
        N = self.n_rec_video

        print(f"\n{'='*50}")
        print(f"为用户{user}生成推荐:")
        print('='*50)

        if user not in self.trainSet:
            print("  用户不在训练集中，使用基于内容的推荐")
            return self._content_based_recommend(user, N)

        watched_videos = set(self.trainSet[user].keys())
        print(f"  已观看视频数: {len(watched_videos)}")

        # 方法1: 基于协同过滤的推荐
        cf_recommendations = self._collaborative_recommend(user, watched_videos, K, N)

        # 方法2: 基于内容的推荐
        cb_recommendations = self._content_based_recommend(user, N)

        # 合并推荐结果
        all_recommendations = {}

        # 添加协同过滤推荐
        for video, score in cf_recommendations:
            all_recommendations[video] = score

        # 添加基于内容的推荐
        for video, score in cb_recommendations:
            if video in all_recommendations:
                all_recommendations[video] = max(all_recommendations[video], score)
            else:
                all_recommendations[video] = score * 0.5  # 降低内容推荐的权重

        # 过滤已观看的视频
        for video in watched_videos:
            all_recommendations.pop(video, None)

        if not all_recommendations:
            print("  没有生成推荐，使用热门视频后备")
            return self._get_popular_videos(watched_videos, N)

        # 按得分排序
        sorted_recommendations = sorted(all_recommendations.items(),
                                       key=lambda x: x[1], reverse=True)

        # 返回前N个
        recommendations = sorted_recommendations[:N]

        # 显示推荐详情
        print(f"  生成 {len(recommendations)} 个推荐:")
        for video, score in recommendations:
            tags = self._get_video_tags(video)
            print(f"    视频{video}: 得分={score:.3f}, 标签={tags}")

        return recommendations

    def _collaborative_recommend(self, user, watched_videos, K, N):
        """基于协同过滤的推荐"""
        if user not in self.user_sim_matrix or not self.user_sim_matrix[user]:
            return []

        # 获取最相似的K个用户
        similar_users = []
        for other_user, sim in self.user_sim_matrix[user].items():
            if sim > 0 and other_user in self.trainSet:
                similar_users.append((other_user, sim))

        if not similar_users:
            return []

        # 按相似度排序
        similar_users.sort(key=lambda x: x[1], reverse=True)
        similar_users = similar_users[:K]

        print(f"  找到 {len(similar_users)} 个相似用户:")
        for other_user, sim in similar_users[:3]:  # 显示前3个
            print(f"    用户{other_user}: 相似度={sim:.3f}")

        # 收集候选视频
        candidate_videos = defaultdict(float)

        for other_user, similarity in similar_users:
            for video, rating in self.trainSet[other_user].items():
                if video in watched_videos:
                    continue

                # 计算得分
                candidate_videos[video] += similarity * rating

        if not candidate_videos:
            return []

        # 归一化得分
        max_score = max(candidate_videos.values())
        if max_score > 0:
            for video in candidate_videos:
                candidate_videos[video] = (candidate_videos[video] / max_score) * 5.0

        return sorted(candidate_videos.items(), key=lambda x: x[1], reverse=True)[:N]

    def _content_based_recommend(self, user, N):
        """基于内容的推荐"""
        if user not in self.user_profiles:
            return []

        user_profile = self.user_profiles[user]
        if not user_profile:
            return []

        # 获取用户前5个兴趣标签
        top_tags = sorted(user_profile.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  用户兴趣标签: {[tag for tag, _ in top_tags]}")

        candidate_videos = defaultdict(float)

        for video, tags in self.video_tags.items():
            if video in self.trainSet.get(user, {}):
                continue

            # 计算视频与用户兴趣的匹配度
            match_score = 0
            for tag, tag_weight in tags.items():
                if tag in user_profile:
                    match_score += user_profile[tag] * tag_weight

            if match_score > 0:
                candidate_videos[video] = match_score

        if not candidate_videos:
            return []

        # 归一化得分
        max_score = max(candidate_videos.values())
        if max_score > 0:
            for video in candidate_videos:
                candidate_videos[video] = (candidate_videos[video] / max_score) * 5.0

        return sorted(candidate_videos.items(), key=lambda x: x[1], reverse=True)[:N]

    def _get_video_tags(self, video_id):
        """获取视频标签"""
        if video_id in self.video_tags:
            tags = self.video_tags[video_id]
            return ', '.join(sorted(tags.keys())[:3])  # 返回前3个标签
        return "无标签"

    def _get_popular_videos(self, watched_videos, N):
        """获取热门视频"""
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

    def save_recommendations(self, db_connection):
        """保存推荐结果到数据库"""
        print("\n" + "="*50)
        print("保存推荐结果到数据库")
        print("="*50)

        if not self.trainSet:
            print("训练集为空，无法生成推荐")
            return

        try:
            cursor = db_connection.cursor()

            # 清空推荐表
            cursor.execute("TRUNCATE TABLE myapp_rec;")
            db_connection.commit()
            print("已清空推荐表")

            # 准备插入语句
            insert_sql = """
                INSERT INTO myapp_rec (user_id, video_id, score, created_at) 
                VALUES (%s, %s, %s, NOW())
            """

            all_recommendations = []

            # 为每个用户生成推荐
            for user_id in self.trainSet.keys():
                recommendations = self.recommend_for_user(user_id)

                for video_id, score in recommendations:
                    try:
                        user_id_int = int(user_id)
                        video_id_int = int(video_id)
                        score_float = float(score)

                        all_recommendations.append((user_id_int, video_id_int, score_float))
                    except (ValueError, TypeError) as e:
                        print(f"数据类型转换错误: user={user_id}, video={video_id}, 错误: {e}")
                        continue

            # 批量插入推荐数据
            if all_recommendations:
                try:
                    cursor.executemany(insert_sql, all_recommendations)
                    db_connection.commit()
                    print(f"\n成功插入 {len(all_recommendations)} 条推荐记录")

                    # 特别检查用户25和27
                    for user_id in [25, 27]:
                        cursor.execute("SELECT COUNT(*) FROM myapp_rec WHERE user_id = %s", (user_id,))
                        count = cursor.fetchone()[0]
                        print(f"  用户{user_id}: {count} 条推荐")

                except Exception as e:
                    print(f"批量插入失败: {e}")
                    db_connection.rollback()

            cursor.close()

        except Exception as e:
            print(f"数据库操作失败: {e}")
            import traceback
            traceback.print_exc()

    def verify_recommendations(self, db_connection):
        """验证推荐结果"""
        print("\n" + "="*50)
        print("验证推荐结果")
        print("="*50)

        try:
            cursor = db_connection.cursor()

            # 检查用户25的推荐
            print("\n1. 用户25的推荐详情:")
            cursor.execute("""
                SELECT r.video_id, r.score, v.title, v.category
                FROM myapp_rec r
                LEFT JOIN study_clean v ON r.video_id = v.id
                WHERE r.user_id = 25
                ORDER BY r.score DESC
            """)

            recs_25 = cursor.fetchall()

            if recs_25:
                print(f"✓ 用户25有 {len(recs_25)} 条推荐:")
                for video_id, score, title, category in recs_25:
                    title_str = str(title) if title else "无标题"
                    category_str = str(category) if category else "无分类"

                    # 判断推荐是否合理
                    if "python" in title_str.lower() or "pandas" in title_str.lower():
                        print(f"  ✓ Python相关: 视频{video_id}, 评分{score:.2f}, '{title_str}' ({category_str})")
                    elif "二次元" in title_str or "动漫" in title_str or "漫展" in title_str:
                        print(f"  ✗ 二次元: 视频{video_id}, 评分{score:.2f}, '{title_str}' ({category_str})")
                    else:
                        print(f"  - 其他: 视频{video_id}, 评分{score:.2f}, '{title_str}' ({category_str})")
            else:
                print("✗ 用户25没有推荐记录")

            # 检查用户27的推荐
            print("\n2. 用户27的推荐详情:")
            cursor.execute("""
                SELECT r.video_id, r.score, v.title, v.category
                FROM myapp_rec r
                LEFT JOIN study_clean v ON r.video_id = v.id
                WHERE r.user_id = 27
                ORDER BY r.score DESC
            """)

            recs_27 = cursor.fetchall()

            if recs_27:
                print(f"✓ 用户27有 {len(recs_27)} 条推荐:")
                for video_id, score, title, category in recs_27:
                    title_str = str(title) if title else "无标题"
                    category_str = str(category) if category else "无分类"

                    # 判断推荐是否合理
                    if "python" in title_str.lower() or "pandas" in title_str.lower():
                        print(f"  ✗ Python相关: 视频{video_id}, 评分{score:.2f}, '{title_str}' ({category_str})")
                    elif "二次元" in title_str or "动漫" in title_str or "漫展" in title_str:
                        print(f"  ✓ 二次元: 视频{video_id}, 评分{score:.2f}, '{title_str}' ({category_str})")
                    else:
                        print(f"  - 其他: 视频{video_id}, 评分{score:.2f}, '{title_str}' ({category_str})")
            else:
                print("✗ 用户27没有推荐记录")

            cursor.close()

        except Exception as e:
            print(f"验证推荐结果失败: {e}")
            import traceback
            traceback.print_exc()


def create_rating_csv_from_db():
    """从数据库读取数据并创建rating.csv文件"""
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
        SELECT user_id, video_id, 5 as rating
        FROM myapp_wishlist
        WHERE user_id IS NOT NULL AND video_id IS NOT NULL
        """
        cursor.execute(sql)
        data = cursor.fetchall()

        print(f"获取到 {len(data)} 条wishlist数据")

        if data:
            # 统计用户25和27的记录
            for user_id in [25, 27]:
                user_count = sum(1 for uid, _, _ in data if uid == user_id)
                print(f"用户{user_id}有 {user_count} 条wishlist记录")

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
    print("混合推荐算法（修正版）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 步骤1: 从数据库创建rating.csv
    data_count = create_rating_csv_from_db()

    if data_count == 0:
        print("错误: 没有从数据库读取到数据")
        return

    # 步骤2: 创建推荐算法实例
    user_cf = UserBasedCF(n_sim_user=0, n_rec_video=9)

    # 步骤3: 加载数据集
    print("\n" + "-" * 40)
    print("加载数据集...")
    user_cf.get_dataset('rating.csv', pivot=0.9)

    # 连接数据库
    try:
        db = pymysql.connect(
            host="localhost",
            user='root',
            password='li974521',
            database='bill_video',
            charset='utf8'
        )

        # 步骤4: 加载视频标签
        print("\n" + "-" * 40)
        user_cf.load_video_tags(db)

        # 步骤5: 构建用户兴趣画像
        print("\n" + "-" * 40)
        user_cf.build_user_profiles()

        # 步骤6: 计算用户相似度
        print("\n" + "-" * 40)
        print("计算用户相似度...")
        user_cf.calc_user_sim_with_content()

        # 步骤7: 生成并保存推荐
        print("\n" + "-" * 40)
        user_cf.save_recommendations(db)

        # 步骤8: 验证推荐结果
        user_cf.verify_recommendations(db)

        db.close()

    except Exception as e:
        print(f"数据库连接失败: {e}")
        return

    print("\n" + "=" * 60)
    print("算法运行完成!")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n提示: 算法运行完成后，请:")
    print("1. 刷新Django推荐页面 (/video_rec/)")
    print("2. 检查myapp_rec表中的推荐结果")
    print("3. 查看控制台输出了解推荐详情")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()