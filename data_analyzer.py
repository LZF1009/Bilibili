import pandas as pd
import os  # 导入 os 模块


class BiliVideoAnalyzer:
    def __init__(self, csv_path="spider/clean.csv"):
        self.csv_path = csv_path
        self.df = None

    def load_dataset(self):
        """加载数据集并进行预处理"""
        try:
            if os.path.exists(self.csv_path):
                self.df = pd.read_csv(self.csv_path)

                # 检查并过滤掉'发布时间戳'列中值为'pubdate'的行
                if '发布时间戳' in self.df.columns:
                    initial_count = len(self.df)
                    self.df = self.df[self.df['发布时间戳'] != 'pubdate']
                    if len(self.df) < initial_count:
                        print(f"已过滤掉 {initial_count - len(self.df)} 行包含'pubdate'的无效数据。")

                # ==================== 新增开始 ====================
                # 确保关键的数字列是数值类型
                numeric_columns = ['点赞人数', '收藏人数', '评论人数', '弹幕数量']
                for col in numeric_columns:
                    if col in self.df.columns:
                        # 使用 pd.to_numeric，并将无法转换的值设为NaN，然后填充为0
                        self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0).astype(int)
                # ==================== 新增结束 ====================

                # 处理发布时间相关字段
                if '发布时间戳' in self.df.columns and not self.df.empty:
                    self.df['发布时间'] = pd.to_datetime(self.df['发布时间戳'], errors='coerce')

                    initial_count = len(self.df)
                    self.df = self.df.dropna(subset=['发布时间'])
                    if len(self.df) < initial_count:
                        print(f"已过滤掉 {initial_count - len(self.df)} 行无效的时间数据。")

                    self.df['发布月份'] = self.df['发布时间'].dt.month
                    self.df['发布年份'] = self.df['发布时间'].dt.year
                    self.df['发布小时'] = self.df['发布时间'].dt.hour

                # 处理视频时长字段（转换为数值）
                if '视频时长(分钟)' in self.df.columns:
                    self.df['时长分钟'] = pd.to_numeric(
                        self.df['视频时长(分钟)'].str.replace(',', '.'),
                        errors='coerce'
                    )

                if not self.df.empty:
                    print(f"数据处理成功，共{len(self.df)}条有效数据")
                else:
                    print("数据处理后为空，请检查CSV文件内容。")
                    self.df = None

            else:
                print(f"CSV文件不存在: {self.csv_path}")
        except Exception as e:
            print(f"加载数据出错: {e}")
            self.df = None

    def get_category_distribution(self):
        """获取视频类别的分布情况"""
        if self.df is None:
            return []
        category_counts = self.df['类别'].value_counts()
        return [{"name": cat, "value": int(count)} for cat, count in category_counts.items()]

    def get_video_type_distribution(self):
        """获取视频类型的分布情况"""
        if self.df is None:
            return []
        type_counts = self.df['视频类型'].value_counts()
        return [{"name": vtype, "value": int(count)} for vtype, count in type_counts.items()]

    def get_top_authors(self, top_n=10):
        """获取Top N作者的统计数据（点赞、收藏等）"""
        if self.df is None:
            return []
        author_stats = self.df.groupby('作者').agg({
            "点赞人数": "sum",
            "收藏人数": "sum",
            "评论人数": "sum",
            "视频ID": "count"
        }).reset_index()
        author_stats = author_stats.sort_values('点赞人数', ascending=False)
        return [
            {
                "name": row["作者"],
                "likes": row["点赞人数"],
                "favorites": row["收藏人数"],
                "comments": row["评论人数"],
                "videos": row["视频ID"]
            }
            for _, row in list(author_stats.iterrows())[:top_n]
        ]

    def get_monthly_trends(self):
        """获取每月的视频数据趋势（数量、点赞等）"""
        if self.df is None or '发布月份' not in self.df.columns:
            return []
        monthly_stats = self.df.groupby('发布月份').agg({
            "视频ID": "count",
            "点赞人数": "sum",
            "收藏人数": "sum",
            "评论人数": "sum"
        }).reset_index()

        months = ["1月", "2月", "3月", "4月", "5月", "6月",
                  "7月", "8月", "9月", "10月", "11月", "12月"]
        result = []

        for i in range(1, 13):
            month_data = monthly_stats[monthly_stats['发布月份'] == i]
            if not month_data.empty:
                result.append({
                    "month": months[i - 1],
                    "videos": int(month_data.iloc[0]["视频ID"]),
                    "likes": int(month_data.iloc[0]["点赞人数"]),
                    "favorites": int(month_data.iloc[0]["收藏人数"]),
                    "comments": int(month_data.iloc[0]["评论人数"])
                })
            else:
                result.append({
                    "month": months[i - 1],
                    "videos": 0,
                    "likes": 0,
                    "favorites": 0,
                    "comments": 0
                })
        return result

    def get_duration_analysis(self):
        """视频时长区间分布分析"""
        if self.df is None or '时长分钟' not in self.df.columns:
            return []
        bins = [0, 5, 10, 20, 30, 60, float('inf')]
        labels = ['0-5分钟', '5-10分钟', '10-20分钟', '20-30分钟', '30-60分钟', '60分钟以上']
        self.df['时长区间'] = pd.cut(self.df['时长分钟'], bins=bins, labels=labels, right=False)
        duration_counts = self.df['时长区间'].value_counts()
        return [
            {"name": str(duration), "value": int(count)}
            for duration, count in duration_counts.items()
            if pd.notna(duration)
        ]

    def get_hourly_distribution(self):
        """视频发布小时分布分析"""
        if self.df is None or '发布小时' not in self.df.columns:
            return []
        hourly_counts = self.df['发布小时'].value_counts().sort_index()
        return [
            {"hour": int(hour), "count": int(count)}
            for hour, count in hourly_counts.items()
        ]

    def get_engagement_analysis(self):
        """互动数据综合分析（总量+均值+分类型统计）"""
        if self.df is None:
            return {}
        self.df['互动总数'] = self.df['点赞人数'] + self.df['收藏人数'] + self.df['评论人数']

        category_engagement = self.df.groupby('类别').agg({
            "点赞人数": "mean",
            "收藏人数": "mean",
            "互动总数": "mean"
        }).round(2)

        return {
            "total_videos": int(len(self.df)),
            "total_likes": int(self.df['点赞人数'].sum()),
            "total_favorites": int(self.df['收藏人数'].sum()),
            "total_comments": int(self.df['评论人数'].sum()),
            "avg_likes": round(self.df['点赞人数'].mean(), 2),
            "avg_favorites": round(self.df['收藏人数'].mean(), 2),
            "avg_comments": round(self.df['评论人数'].mean(), 2),
            "category_engagement": category_engagement.to_dict('index')
        }

    def get_top_videos(self, metric="点赞人数", top_n=10):
        """获取指定指标下的Top N视频"""
        if self.df is None:
            return []
        top_videos = self.df.nlargest(top_n, metric)
        return [
            {
                "title": row["标题"],
                "author": row["作者"],
                "likes": int(row["点赞人数"]),
                "favorites": int(row["收藏人数"]),
                "comments": int(row["评论人数"]),
                "category": row["类别"],
                "video_type": row["视频类型"]
            }
            for _, row in top_videos.iterrows()
        ]

    def get_tag_analysis(self, top_n=50):
        """视频标签词频分析（取Top N标签）"""
        if self.df is None or '标签' not in self.df.columns:
            return []
        all_tags = []
        for tags in self.df['标签'].dropna():
            if isinstance(tags, str):
                tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
                all_tags.extend(tag_list)

        tag_counts = pd.Series(all_tags).value_counts().head(top_n)
        return [
            {"name": tag, "value": int(count)}
            for tag, count in tag_counts.items()
        ]

    def get_dashboard_data(self):
        """整合所有分析数据，返回仪表盘所需的完整数据集"""
        self.load_dataset()
        return {
            "category_distribution": self.get_category_distribution(),
            "video_type_distribution": self.get_video_type_distribution(),
            "top_authors": self.get_top_authors(),
            "monthly_trends": self.get_monthly_trends(),
            "duration_analysis": self.get_duration_analysis(),
            "hourly_distribution": self.get_hourly_distribution(),
            "engagement_analysis": self.get_engagement_analysis(),
            "top_videos": self.get_top_videos(),
            "tag_analysis": self.get_tag_analysis()
        }


# 调用示例：生成仪表盘数据
if __name__ == "__main__":
    # 改为正确的路径：spider/clean.csv
    analyzer = BiliVideoAnalyzer(csv_path="BlBl/spiders/clean.csv")
    dashboard_data = analyzer.get_dashboard_data()
    if dashboard_data['category_distribution']: # 检查数据是否加载成功
        print("仪表盘数据生成完成！")
        print(f" - 总视频数: {dashboard_data['engagement_analysis']['total_videos']}")
        print(f" - 总点赞数: {dashboard_data['engagement_analysis']['total_likes']}")
    else:
        print("未能生成仪表盘数据，请检查CSV文件路径和内容。")