import tkinter as tk
from tkinter import Toplevel
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore # google.cloud에서 firestore를 직접 가져옵니다.
import random
import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- [설정] 최종 설정 값 ---
# 1. 서비스 계정 키 파일의 실제 이름을 정확하게 입력해주세요.
#    이 파일은 main_app.py와 같은 폴더에 있어야 합니다.
KEY_FILE_PATH = "csproject2025-cfcb7-firebase-adminsdk-fbsvc-f15f257ae3.json" 

# 2. 접속할 Firestore 데이터베이스 인스턴스 ID
TARGET_DB_ID = "csproject2025" 

# 3. 테스트할 사용자 ID
TEST_USER_ID = "user1" 
# ----------------------------------------------------

# --- Firebase 초기화 ---
project_id_from_key = "알 수 없음" 
db = None # db 변수를 먼저 정의
try:
    cred_obj_for_admin_sdk = credentials.Certificate(KEY_FILE_PATH)
    project_id_from_key = cred_obj_for_admin_sdk.project_id 
    print(f"✅ Admin SDK 인증서 객체 로드 성공. 프로젝트 ID: '{project_id_from_key}'")

    if not firebase_admin._apps:
        app = firebase_admin.initialize_app(cred_obj_for_admin_sdk)
        print("✅ Firebase 앱 초기화 성공 (새로 초기화).")
    else:
        app = firebase_admin.get_app()
        print(f"✅ Firebase 앱 초기화 성공 (기존 앱 사용 - 프로젝트 ID: '{app.project_id}').")
    
    gcloud_credentials = app.credential.get_credential()
    print("✅ google-auth 호환 인증서 가져오기 성공.")

    db = firestore.Client(project=project_id_from_key, credentials=gcloud_credentials, database=TARGET_DB_ID)
    print(f"✅ Firestore 클라이언트 생성 성공 (타겟 DB: '{TARGET_DB_ID}', 프로젝트: '{project_id_from_key}').")
    print("   -> 이제 메인 앱이 정상적으로 Firestore에 연결되었습니다!")

except Exception as e:
    print(f"🚨🚨🚨 Firebase 또는 Firestore 클라이언트 초기화 실패! 🚨🚨🚨")
    print(f"에러 내용: {e}")
    # db는 이미 None으로 초기화되어 있음
# --- Firebase 초기화 끝 ---


# --- 사용자 피드백을 받는 다이얼로그 UI 클래스 ---
class FeedbackDialog(Toplevel):
    def __init__(self, parent, trend):
        super().__init__(parent)
        self.title(f"'{trend.get('keyword', 'N/A')}' 피드백"); self.geometry("320x180"); self.transient(parent); self.grab_set()
        self.trend = trend; self.rating = 0; self.result = None
        self.empty_star = "\u2606"; self.filled_star = "\u2605"
        tk.Label(self, text=f"'{trend.get('keyword', 'N/A')}'에 대한 만족도를 평가해주세요:", font=("Helvetica", 10)).pack(pady=10)
        star_frame = tk.Frame(self); star_frame.pack(pady=5); self.stars = []
        for i in range(5):
            star_label = tk.Label(star_frame, text=self.empty_star, font=("Helvetica", 24), fg="gray"); star_label.pack(side="left", padx=2)
            star_label.bind("<Button-1>", lambda e, index=i: self._on_star_click(index)); self.stars.append(star_label)
        button_frame = tk.Frame(self); button_frame.pack(pady=15)
        tk.Button(button_frame, text="확인", command=self._confirm).pack(side="left", padx=10)
        tk.Button(button_frame, text="관심 없음", command=self._not_interested).pack(side="left", padx=10)
        tk.Button(button_frame, text="취소", command=self._cancel).pack(side="left", padx=10)
    def _update_stars(self, rating_limit):
        for i, star in enumerate(self.stars):
            if i < rating_limit: star.config(text=self.filled_star, fg="gold")
            else: star.config(text=self.empty_star, fg="gray")
    def _on_star_click(self, index): self.rating = index + 1; self._update_stars(self.rating)
    def _confirm(self):
        if self.rating == 0: return
        self.result = {'type': 'rating', 'value': self.rating}; self.destroy()
    def _not_interested(self): self.result = {'type': 'not_interested'}; self.destroy()
    def _cancel(self): self.result = None; self.destroy()


# --- 메인 애플리케이션 UI 및 로직 클래스 ---
class PersonalizedRecommenderApp:
    def __init__(self, root, user_id):
        if not db:
            print("Firestore 클라이언트(db)가 초기화되지 않아 앱을 시작할 수 없습니다.")
            root.destroy()
            if __name__ == '__main__': # 스크립트 직접 실행 시에만 sys.exit 호출
                 sys.exit(1)
            return

        self.root = root; self.root.title("콘텐츠 기반 개인화 추천"); self.root.geometry("400x550")
        self.user_id = user_id; self.user_profile = None; self.trends_cache = []
        
        self.vectorizer = None
        self.cosine_sim_matrix = None
        # keyword_to_matrix_idx는 summary가 있는 트렌드만 포함하여 유사도 행렬의 인덱스와 매핑합니다.
        self.keyword_to_matrix_idx = {} 
        # trends_cache_indices는 trends_cache의 원래 인덱스를 저장합니다.
        self.trends_cache_indices_for_model = []


        self.trend_frame = tk.Frame(root, pady=5); self.trend_frame.pack(pady=10, padx=10, fill="x")
        self.info_label = tk.Label(root, text="데이터를 불러오는 중...", font=("Helvetica", 10), fg="blue"); self.info_label.pack(pady=5)
        
        self.load_initial_data()

    def _build_similarity_model(self):
        print("--- [유사도 모델 구축 시작] ---")
        # summary가 있고, keyword도 있는 문서만 필터링
        summaries_data = []
        self.trends_cache_indices_for_model = [] # 모델 구축에 사용된 문서의 원래 인덱스
        
        for idx, trend_doc in enumerate(self.trends_cache):
            if trend_doc.get('summary') and trend_doc.get('keyword'):
                summaries_data.append(trend_doc['summary'])
                self.keyword_to_matrix_idx[trend_doc['keyword']] = len(self.trends_cache_indices_for_model)
                self.trends_cache_indices_for_model.append(idx)
        
        if len(summaries_data) < 2:
            print("경고: 유사도 모델을 만들기에 summary 데이터가 부족합니다 (최소 2개 필요).")
            self.vectorizer = None; self.cosine_sim_matrix = None; return

        try:
            self.vectorizer = TfidfVectorizer(min_df=1) # 문서가 적을 수 있으므로 min_df=1
            tfidf_matrix = self.vectorizer.fit_transform(summaries_data)
            self.cosine_sim_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
            print(f"✅ 유사도 모델 구축 완료. (대상 문서 수: {len(summaries_data)})")
        except Exception as e:
            print(f"🚨 유사도 모델 구축 중 에러: {e}")
            self.vectorizer = None; self.cosine_sim_matrix = None
        print("--- [유사도 모델 구축 완료] ---")

    def load_initial_data(self):
        print("--- [데이터 로딩 시작] ---")
        try:
            trends_ref = db.collection('trend').stream()
            self.trends_cache = [doc.to_dict() for doc in trends_ref]
            if not self.trends_cache: print("경고: 'trend' 컬렉션은 찾았지만, 문서가 하나도 없습니다.")
            else: print(f"'trend' 컬렉션에서 {len(self.trends_cache)}개의 문서를 로드했습니다.")
        except Exception as e: print(f"에러: 'trend' 컬렉션 조회 중 에러 발생: {e}"); self.trends_cache = []
        
        self._build_similarity_model() # summary 기반 유사도 모델 구축
        self.fetch_user_profile()
        self.display_recommendations()
        print("--- [데이터 로딩 완료] ---")


    def fetch_user_profile(self):
        try:
            user_ref = db.collection('user').document(self.user_id)
            doc = user_ref.get()
            if doc.exists: self.user_profile = doc.to_dict()
            else: self.user_profile = None; print(f"경고: 'user' 컬렉션에서 '{self.user_id}' 문서를 찾을 수 없습니다.")
        except Exception as e: print(f"에러: '{self.user_id}' 문서 조회 중 에러 발생: {e}"); self.user_profile = None

    def display_recommendations(self):
        for widget in self.trend_frame.winfo_children(): widget.destroy()
        NUM_TO_DISPLAY = 3
        final_recommend_items_with_scores = []
        info_text = ""

        if not self.trends_cache:
            tk.Label(self.trend_frame, text="표시할 트렌드가 없습니다.", font=("Helvetica", 12)).pack(anchor="w")
            self.info_label.config(text="DB에 트렌드를 추가해주세요."); return

        # 모든 트렌드에 대한 기본 점수 초기화
        # 점수를 trends_cache의 인덱스 기준으로 관리
        trend_scores = np.zeros(len(self.trends_cache))

        if not self.user_profile:
            tk.Label(self.trend_frame, text="일반 트렌드 (랜덤)", font=("Helvetica", 12)).pack(anchor="w")
            # 랜덤 샘플링 시 인덱스 사용
            if self.trends_cache:
                 sampled_indices = random.sample(range(len(self.trends_cache)), min(len(self.trends_cache), NUM_TO_DISPLAY))
                 final_recommend_items_with_scores = [{'trend_data': self.trends_cache[i], 'score': 0} for i in sampled_indices]
            info_text = "피드백을 남겨주시면 취향에 맞는 트렌드를 추천해 드려요."
        else:
            tk.Label(self.trend_frame, text=f"{self.user_profile.get('name', '')}님 맞춤 트렌드", font=("Helvetica", 12)).pack(anchor="w")
            preferred = self.user_profile.get('preferredTopics', []) or []
            avoided = self.user_profile.get('avoidTopics', []) or []

            # 1. 명시적 선호/회피 점수 반영
            for idx, trend_doc in enumerate(self.trends_cache):
                keyword = trend_doc.get('keyword')
                if not keyword: continue
                if keyword in preferred: trend_scores[idx] += 100  # 강한 긍정
                if keyword in avoided: trend_scores[idx] = -1000 # 강한 부정 (사실상 제외되도록 매우 낮은 점수)

            # 2. 콘텐츠 유사도 기반 점수 반영
            if self.cosine_sim_matrix is not None and preferred:
                for pref_keyword in preferred:
                    # pref_keyword가 유사도 모델 구축 시 사용된 키워드인지 확인 (summary가 있었는지)
                    if pref_keyword in self.keyword_to_matrix_idx:
                        # 유사도 행렬에서의 인덱스
                        pref_matrix_idx = self.keyword_to_matrix_idx[pref_keyword]
                        # 유사도 행렬로부터 유사도 벡터 가져오기
                        similarity_vector_for_pref = self.cosine_sim_matrix[pref_matrix_idx]
                        
                        # 모든 트렌드에 대해 유사도 점수 적용
                        for i, target_trend_original_idx in enumerate(self.trends_cache_indices_for_model):
                            # target_trend_original_idx는 trends_cache에서의 원래 인덱스
                            # similarity_vector_for_pref[i]는 pref_keyword와 target_trend 간의 유사도
                            
                            # 자기 자신에 대한 유사도 부스팅은 제외 (이미 명시적 선호로 +100점)
                            target_keyword = self.trends_cache[target_trend_original_idx].get('keyword')
                            if target_keyword == pref_keyword:
                                continue
                            
                            if target_keyword not in avoided:
                                trend_scores[target_trend_original_idx] += similarity_vector_for_pref[i] * 20 # 유사도 가중치
            
            # 점수 기반으로 정렬된 아이템 리스트 생성
            for idx, score in enumerate(trend_scores):
                keyword = self.trends_cache[idx].get('keyword')
                if keyword and keyword not in avoided : # 최종적으로 회피 목록 제외
                    final_recommend_items_with_scores.append({'trend_data': self.trends_cache[idx], 'score': score})
            
            final_recommend_items_with_scores.sort(key=lambda x: x['score'], reverse=True)
            
            if any(item['trend_data'].get('keyword') in preferred for item in final_recommend_items_with_scores[:NUM_TO_DISPLAY]):
                info_text = "취향과 콘텐츠 유사도를 반영한 추천입니다."
            elif final_recommend_items_with_scores:
                info_text = "새로운 트렌드를 탐색해보세요!"
            else:
                info_text = "추천할 트렌드가 없습니다."

        self.info_label.config(text=info_text)
        for item in final_recommend_items_with_scores[:NUM_TO_DISPLAY]:
            trend_item = item['trend_data']
            if 'keyword' in trend_item:
                button = tk.Button(self.trend_frame, text=trend_item['keyword'], font=("Helvetica", 10), 
                                   command=lambda t=trend_item: self.open_feedback_dialog(t))
                button.pack(fill="x", pady=3, ipady=5)

    def open_feedback_dialog(self, trend):
        dialog = FeedbackDialog(self.root, trend); self.root.wait_window(dialog)
        if dialog.result: self.update_user_preference(trend.get('keyword'), dialog.result) # .get 추가

    def update_user_preference(self, keyword, result):
        if not keyword: return # 키워드가 없는 경우 처리 중단
        user_ref = db.collection('user').document(self.user_id)
        update_data = {}
        feedback_type, value = result['type'], result.get('value')
        if feedback_type == 'rating' and value:
            if value >= 4: update_data.update({'preferredTopics': firestore.ArrayUnion([keyword]), 'avoidTopics': firestore.ArrayRemove([keyword])})
            elif value <= 2: update_data.update({'avoidTopics': firestore.ArrayUnion([keyword]), 'preferredTopics': firestore.ArrayRemove([keyword])})
        elif feedback_type == 'not_interested': update_data.update({'avoidTopics': firestore.ArrayUnion([keyword]), 'preferredTopics': firestore.ArrayRemove([keyword])})
        if update_data: 
            user_ref.update(update_data)
            print(f"✅ DB 업데이트: {keyword} - {update_data}")
            self.fetch_user_profile(); self.display_recommendations()

# --- 프로그램 실행 ---
if __name__ == "__main__":
    if db is None: # KEY_FILE_PATH 경로가 틀렸거나, TARGET_DB_ID가 틀렸거나 등등
        print("\n[실행 전 확인!] Firebase 클라이언트(db)가 초기화되지 않았습니다.")
        sys.exit(1)
    root = tk.Tk()
    app = PersonalizedRecommenderApp(root, user_id=TEST_USER_ID)
    root.mainloop()