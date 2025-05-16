import pandas as pd
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict

def filter_keywords_by_language(csv_path):
    """
    CSV 파일에서 키워드를 불러와 언어 필터링 및 클러스터링을 수행합니다.
    """
    # CSV 파일 로드
    try:
        df = pd.read_csv(csv_path)
        # 첫 번째 열을 키워드로 사용 (CSV 구조에 따라 조정 필요)
        keywords = df.iloc[:, 0].tolist()
        print(f"원본 키워드 총 개수: {len(keywords)}")
    except Exception as e:
        print(f"CSV 파일 로드 중 오류: {e}")
        return None
        
    # 언어 필터링
    filtered_data = []
    ko_count = 0
    en_count = 0
    other_count = 0
    
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
            
        # 한글이 있으면 한국어로 간주
        if re.search(r'[가-힣]', keyword):
            filtered_data.append({'keyword': keyword, 'language': 'ko'})
            ko_count += 1
        # 영어만 있으면 영어로 간주
        elif re.search(r'^[a-zA-Z0-9\s.,!?:;\'\"\-_&]+$', keyword):
            filtered_data.append({'keyword': keyword, 'language': 'en'})
            en_count += 1
        else:
            other_count += 1
    
    # 필터링 결과를 데이터프레임으로 변환
    filtered_df = pd.DataFrame(filtered_data)
    
    print(f"필터링 후 총 개수: {len(filtered_data)} (원본 대비 {len(filtered_data)/len(keywords)*100:.1f}% 유지)")
    print(f"한국어: {ko_count}개")
    print(f"영어: {en_count}개")
    print(f"제외된 기타 언어: {other_count}개")
    
    if filtered_df.empty:
        print("필터링 후 남은 키워드가 없습니다.")
        return None
    
    # 키워드 텍스트만 추출하여 벡터화
    keywords_list = filtered_df['keyword'].tolist()
    
    # TF-IDF 벡터화 (문자 수준 n-gram으로 언어 간 유사성 포착)
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3))
    tfidf_matrix = vectorizer.fit_transform(keywords_list)
    
    # 코사인 유사도 계산
    similarity_matrix = cosine_similarity(tfidf_matrix)
    
    # 거리 행렬로 변환 (유사도가 높을수록 거리는 짧음)
    # 모든 값이 0 이상이 되도록 보장
    distance_matrix = np.clip(1 - similarity_matrix, 0, None)
    
    # DBSCAN 클러스터링
    clustering = DBSCAN(eps=0.5, min_samples=1, metric='precomputed').fit(distance_matrix)
    
    # 클러스터 레이블 할당
    filtered_df['cluster'] = clustering.labels_
    
    return filtered_df

def print_clustering_results(df):
    """
    클러스터링 결과를 깔끔하게 출력합니다.
    """
    print(f"\n===== 클러스터링 결과 =====")
    print(f"총 키워드 수: {len(df)}")
    print(f"클러스터 수: {len(df['cluster'].unique())}")
    
    # 클러스터 크기 분석
    cluster_sizes = df['cluster'].value_counts().to_dict()
    
    # 클러스터 크기별 통계
    singleton_clusters = sum(1 for size in cluster_sizes.values() if size == 1)
    multi_item_clusters = sum(1 for size in cluster_sizes.values() if size > 1)
    
    print(f"단일 항목 클러스터: {singleton_clusters}개")
    print(f"다중 항목 클러스터: {multi_item_clusters}개")
    
    # 가장 큰 클러스터 찾기
    if multi_item_clusters > 0:
        largest_cluster_id = max(cluster_sizes.items(), key=lambda x: x[1])[0]
        largest_cluster_size = cluster_sizes[largest_cluster_id]
        print(f"가장 큰 클러스터: 클러스터 {largest_cluster_id} ({largest_cluster_size}개 항목)")
    
    # 클러스터별로 정렬
    df_sorted = df.sort_values(['cluster', 'language', 'keyword'])
    
    # 클러스터별 출력
    for cluster_id in sorted(df_sorted['cluster'].unique()):
        cluster_items = df_sorted[df_sorted['cluster'] == cluster_id]
        print(f"\n## 클러스터 {cluster_id} ({len(cluster_items)}개)")
        
        # 언어별로 구분
        ko_items = cluster_items[cluster_items['language'] == 'ko']
        en_items = cluster_items[cluster_items['language'] == 'en']
        
        if not ko_items.empty:
            print("한국어:")
            for keyword in ko_items['keyword']:
                print(f"- {keyword}")
                
        if not en_items.empty:
            print("영어:")
            for keyword in en_items['keyword']:
                print(f"- {keyword}")

def prioritize_keywords(df):
    """
    클러스터링된 키워드에 점수를 매겨 우선순위를 정합니다.
    """
    print("\n===== 키워드 우선순위 설정 =====")
    
    # 클러스터 정보를 활용한 점수화
    # 1. 클러스터 크기 점수 계산 (클러스터가 크면 인기 있는 주제일 가능성이 높음)
    cluster_sizes = df['cluster'].value_counts().to_dict()
    df['cluster_size'] = df['cluster'].map(cluster_sizes)
    df['cluster_score'] = df['cluster_size'] / df['cluster_size'].max()
    
    # 2. 특수성 점수 - 단어 수가 많을수록 더 구체적인 쿼리일 가능성이 높음
    df['word_count'] = df['keyword'].str.split().str.len()
    # 단어 수가 1인 경우는 기본값 1.0, 그 이상은 1.0 + 0.1 * (단어 수 - 1)로 계산
    df['specificity_score'] = 1.0 + 0.1 * (df['word_count'] - 1)
    
    # 3. 주제별 가중치 조정
    
    # a. 날씨 관련 키워드 가중치 감소
    weather_terms = ['날씨', 'weather', '일기예보', '오늘의 날씨', '초단기', '장마']
    df['is_weather'] = df['keyword'].isin(weather_terms)
    df.loc[df['is_weather'], 'specificity_score'] *= 0.6
    
    # b. 스포츠 경기 결과 패턴에 대한 가중치 감소
    # "~대 ~", "~vs~", "~ vs ~" 패턴 식별
    sports_pattern1 = r'대\s+'  # "~대 ~" 패턴
    sports_pattern2 = r'vs'     # "~vs~" 또는 "~ vs ~" 패턴
    
    # 패턴이 있는 키워드 식별
    df['is_sports_match'] = (
        df['keyword'].str.contains(sports_pattern1, regex=True) | 
        df['keyword'].str.contains(sports_pattern2, regex=True, case=False)
    )
    
    # 경기 결과 관련 키워드의 점수 감소 (0.6의 가중치)
    df.loc[df['is_sports_match'], 'specificity_score'] *= 0.6
    df.loc[df['is_sports_match'], 'cluster_score'] *= 0.7
    
    # 4. 클러스터별 대표 키워드 선택
    # 각 클러스터에서 가장 높은 점수를 가진 키워드 선택
    df['temp_score'] = (df['specificity_score'] + df['cluster_score']) / 2
    
    # 클러스터별 대표 키워드 선택
    representative_keywords = []
    for cluster_id in df['cluster'].unique():
        cluster_df = df[df['cluster'] == cluster_id]
        
        # 클러스터 크기가 1이면 해당 키워드 선택
        if len(cluster_df) == 1:
            representative_keywords.append(cluster_df.iloc[0]['keyword'])
        else:
            # 클러스터 내에서 점수가 가장 높은 키워드 선택
            best_keyword = cluster_df.loc[cluster_df['temp_score'].idxmax()]['keyword']
            representative_keywords.append(best_keyword)
    
    # 대표 키워드 데이터프레임 생성
    rep_df = df[df['keyword'].isin(representative_keywords)].copy()
    
    # 5. 최종 점수 계산
    # 클러스터 점수와 특수성 점수의 가중 평균 (글자수 가중치 제거)
    rep_df['final_score'] = (0.6 * rep_df['cluster_score'] + 
                             0.4 * rep_df['specificity_score'])
    
    # 점수에 따라 정렬
    rep_df = rep_df.sort_values('final_score', ascending=False)
    
    # 상위 50개 키워드만 선택
    max_requests = 50  # 상위 50개만 선택
    top_keywords = rep_df.head(max_requests)
    
    # 결과 출력
    print(f"\n총 클러스터 수: {len(df['cluster'].unique())}")
    print(f"선택된 대표 키워드 수: {len(rep_df)}")
    print(f"최종 선택된 상위 키워드 수: {len(top_keywords)}")
    
    # 선택된 키워드와 점수 출력
    print("\n상위 20개 우선 키워드:")
    for i, (_, row) in enumerate(top_keywords.head(20).iterrows()):
        tag = ""
        if row.get('is_sports_match', False):
            tag += " [스포츠경기]"
        if row.get('is_weather', False):
            tag += " [날씨]"
            
        print(f"{i+1}. {row['keyword']}{tag} (점수: {row['final_score']:.2f}, 클러스터 크기: {row['cluster_size']})")
    
    # 선택된 키워드 저장 - 순위 정보 포함
    top_keywords.reset_index(drop=True, inplace=True)
    top_keywords['rank'] = top_keywords.index + 1
    top_keywords[['rank', 'keyword', 'final_score']].to_csv("prioritized_keywords.csv", index=False)
    print("\n우선순위가 높은 키워드가 'prioritized_keywords.csv'에 저장되었습니다.")
    
    return top_keywords[['keyword', 'final_score']]

def main():
    # CSV 파일 경로
    csv_path = "google_trends_20250516_162603.csv"
    
    # 1. 필터링 및 클러스터링 수행
    filtered_df = filter_keywords_by_language(csv_path)
    
    if filtered_df is not None:
        # 2. 클러스터링 결과 출력
        print_clustering_results(filtered_df)
        
        # 3. 키워드 우선순위 설정
        prioritized_keywords = prioritize_keywords(filtered_df)
        
        # 4. 필터링된 모든 키워드 저장 (순위 정보 포함)
        all_keywords_df = filtered_df[['keyword']].copy()
        all_keywords_df.reset_index(drop=True, inplace=True)
        all_keywords_df['rank'] = all_keywords_df.index + 1
        all_keywords_df[['rank', 'keyword']].to_csv("filtered_all_keywords.csv", index=False)
        print("\n모든 필터링된 키워드가 'filtered_all_keywords.csv'에 저장되었습니다.")

if __name__ == "__main__":
    main()