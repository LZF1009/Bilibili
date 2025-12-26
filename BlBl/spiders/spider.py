import csv
import time
import random
import os
from datetime import datetime
from bilibili_api import search, sync


def spider_with_api(page, keyword):
    """使用 bilibili-api-python 库来爬取指定页码和关键词的搜索结果"""
    try:
        print(f"--- 正在爬取关键词 '{keyword}' 的第 {page} 页 ---")
        result = sync(search.search_by_type(
            keyword=keyword,
            search_type=search.SearchObjectType.VIDEO,
            page=page,
            page_size=20
        ))
        # 检查是否获取到有效数据
        if result and 'result' in result and result['result']:
            print(f"关键词 '{keyword}' 第 {page} 页爬取成功，获取 {len(result['result'])} 条数据。")
            return result
        else:
            print(f"关键词 '{keyword}' 第 {page} 页无有效数据或已到达最后一页。")
            return None

    except Exception as e:
        print(f"关键词 '{keyword}' 第 {page} 页爬取失败: {e}")
        return None


def scrape_and_save_to_csv(keywords, total_pages_per_keyword):
    """
    爬取多个关键词的数据，并将所有结果保存到单个CSV文件中。
    :param keywords: 要爬取的关键词列表
    :param total_pages_per_keyword: 每个关键词要爬取的页数
    """
    # 按你指定的字段定义表头（新增视频地址、图片地址）
    fieldnames = [
        "aid", "arcurl", "author", "description", "duration",
        "damaku", "collect", "like", "img_url", "pubdate",
        "review", "tag", "title", "typename", "keyword"
    ]

    # 定义最终的文件名
    filename = "data3.csv"

    # 标记文件是否是第一次创建，用于决定是否写入表头
    is_file_new = not os.path.exists(filename)

    # 循环处理每一个关键词
    for keyword in keywords:
        print(f"\n========== 开始处理关键词: '{keyword}' ==========")

        # 循环爬取当前关键词的每一页
        for page in range(1, total_pages_per_keyword + 1):
            raw_result = spider_with_api(page, keyword)

            if raw_result and 'result' in raw_result:
                video_list = raw_result['result']

                # 使用 'a' (append) 模式打开文件，实现数据追加
                with open(filename, 'a', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    # 如果是新文件，在写入第一组数据前先写入表头
                    if is_file_new:
                        writer.writeheader()
                        is_file_new = False  # 写入后就标记为非新文件

                    # 遍历当前页的视频列表，写入CSV
                    for video in video_list:
                        pub_date = datetime.fromtimestamp(video['pubdate']).strftime('%Y-%m-%d %H:%M:%S')
                        row_data = {
                            "aid": video.get('aid', ''),
                            "arcurl": video.get('arcurl', ''),  # 新增：视频地址
                            "author": video.get('author', ''),
                            "description": video.get('description', ''),
                            "duration": video.get('duration', ''),
                            "damaku": video.get('danmaku', ''),
                            "collect": video.get('favorites', ''),
                            "like": video.get('like', ''),
                            "img_url": video.get('pic', ''),  # 新增：图片地址
                            "pubdate": pub_date,
                            "review": video.get('review', ''),
                            "tag": video.get('tag', ''),
                            "title": video['title'].replace('<em class="keyword">', '').replace('</em>', ''),
                            "typename": video.get('typename', ''),
                            "keyword": keyword  # 标记数据所属关键词
                        }
                        writer.writerow(row_data)

            # 在爬取完一页后，随机暂停一段时间
            sleep_time = random.uniform(0.5, 1.5)  # 暂停0.5到1.5秒
            print(f"等待 {sleep_time:.2f} 秒后继续爬取下一页...")
            time.sleep(sleep_time)

        print(f"========== 关键词 '{keyword}' 处理完毕 ==========\n")

    print(f"\n所有关键词的数据爬取完成！")
    print(f"所有结果已合并保存到：{filename}")


# --- 主程序 ---
if __name__ == "__main__":
    # 定义要爬取的关键词列表
    #target_keywords = ['pandas教程', 'Flask框架', '机器学习算法', '网络爬虫', '高数', '英雄联盟', '王者荣耀']
    target_keywords = ['热门动漫','二次元','漫展']
    # 定义每个关键词要爬取的页数
    number_of_pages = 25

    print(f"开始爬取 {len(target_keywords)} 个关键词，每个关键词爬取 {number_of_pages} 页...")
    scrape_and_save_to_csv(target_keywords, number_of_pages)
    print("\n程序全部执行完毕。")