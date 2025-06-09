import tkinter as tk
from tkinter import Toplevel, ttk, messagebox
import requests
import sys

API_BASE_URL = "http://localhost:5001"

def center_window(window, width, height):
    """주어진 너비와 높이를 가진 창을 화면 중앙에 배치합니다."""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    window.geometry(f'{width}x{height}+{x}+{y}')

def run_app():
    try:
        requests.get(API_BASE_URL, timeout=3); print("✅ API 서버 연결 확인됨.")
        login_root = tk.Tk(); LoginWindow(login_root); login_root.mainloop()
    except requests.exceptions.RequestException:
        print("🚨 API 서버에 연결할 수 없습니다."); print("   먼저 다른 터미널에서 'python api_server.py'를 실행해주세요."); sys.exit(1)

class FeedbackDialog(Toplevel):
    def __init__(self, parent, book_info):
        super().__init__(parent); self.title(f"피드백 남기기"); self.geometry("320x180"); self.transient(parent); self.grab_set()
        self.book_info = book_info; self.rating = 0; self.result_rating = None; self.empty_star = "\u2606"; self.filled_star = "\u2605"
        tk.Label(self, text=f"'{book_info.get('title', 'N/A')}'\n책에 대한 만족도를 평가해주세요:", font=("Helvetica", 10)).pack(pady=10)
        star_frame = tk.Frame(self); star_frame.pack(pady=5); self.stars = []
        for i in range(5):
            star_label = tk.Label(star_frame, text=self.empty_star, font=("Helvetica", 24), fg="gray"); star_label.pack(side="left", padx=2)
            star_label.bind("<Button-1>", lambda e, index=i: self._on_star_click(index)); self.stars.append(star_label)
        button_frame = tk.Frame(self); button_frame.pack(pady=15)
        tk.Button(button_frame, text="확인", command=self._confirm).pack(side="left", padx=10)
        tk.Button(button_frame, text="취소", command=self._cancel).pack(side="left", padx=10)
    def _update_stars(self, r):
        for i, s in enumerate(self.stars): s.config(text=(self.filled_star if i<r else self.empty_star), fg=("gold" if i<r else "gray"))
    def _on_star_click(self, index): self.rating = index + 1; self._update_stars(self.rating)
    def _confirm(self):
        if self.rating == 0: messagebox.showwarning("알림", "별점을 선택해주세요.", parent=self); return
        self.result_rating = self.rating; self.destroy()
    def _cancel(self): self.result_rating = None; self.destroy()

class NewUserDialog(Toplevel):
    def __init__(self, parent, login_window_instance):
        super().__init__(parent); self.title("신규 사용자 생성"); self.geometry("450x300"); self.transient(parent); self.grab_set()
        self.login_window = login_window_instance # 콜백을 위한 로그인 창 인스턴스
        self.result_user_id = None; self.entries = {}
        frame = tk.Frame(self, padx=10, pady=10); frame.pack(expand=True, fill="both")
        fields = {"user_id": "사용자 ID*", "name": "이름*", "age_group": "연령대", "reading_frequency": "독서 빈도", "preferred_keywords": "선호 키워드 (,로 구분)", "preferred_types": "선호 타입 (,로 구분)"}
        for i, (key, text) in enumerate(fields.items()):
            tk.Label(frame, text=text).grid(row=i, column=0, sticky="w", pady=2)
            entry = tk.Entry(frame, width=45); entry.grid(row=i, column=1, sticky="w", pady=2); self.entries[key] = entry
        button_frame = tk.Frame(frame); button_frame.grid(row=len(fields), columnspan=2, pady=10)
        tk.Button(button_frame, text="저장", command=self._save).pack(side="left", padx=10)
        tk.Button(button_frame, text="취소", command=self.destroy).pack(side="left", padx=10)
    def _save(self):
        data = {k: (([i.strip() for i in v.get().split(',') if i.strip()]) if 'keywords' in k or 'types' in k else v.get().strip()) for k, v in self.entries.items()}
        if not data.get('user_id') or not data.get('name'): messagebox.showerror("입력 오류", "사용자 ID와 이름은 필수입니다.", parent=self); return
        try:
            response = requests.post(f"{API_BASE_URL}/api/users", json=data); response.raise_for_status()
            self.result_user_id = data['user_id']; messagebox.showinfo("성공", f"사용자 '{self.result_user_id}' 생성 완료.", parent=self)
            self.login_window.refresh_users_and_select(self.result_user_id) # 로그인 창 목록 새로고침
            self.destroy()
        except Exception as e: messagebox.showerror("생성 실패", f"오류 발생:\n{e}", parent=self)

class LoginWindow:
    def __init__(self, root):
        self.root = root; self.root.title("시작하기"); center_window(self.root, 300, 180)
        tk.Label(root, text="작업을 선택해주세요", font=("Helvetica", 14)).pack(pady=15)
        button_frame = tk.Frame(root); button_frame.pack(pady=10)
        tk.Button(button_frame, text="신규 사용자 생성", command=self.open_new_user_dialog).pack(fill="x", pady=3)
        tk.Button(button_frame, text="시작하기", command=self.open_user_selection).pack(fill="x", pady=3)
    def open_new_user_dialog(self):
        NewUserDialog(self.root, self)
    def open_user_selection(self):
        self.root.destroy(); user_select_root = tk.Tk(); UserSelectionWindow(user_select_root); user_select_root.mainloop()
    def refresh_users_and_select(self, new_user_id): pass # UserSelectionWindow가 이 역할을 함

class UserSelectionWindow:
    def __init__(self, root):
        self.root = root; self.root.title("사용자 선택"); center_window(self.root, 300, 200)
        self.selected_user = tk.StringVar()
        tk.Label(root, text="사용자를 선택하세요:", font=("Helvetica", 11)).pack(pady=10)
        self.user_dropdown = ttk.Combobox(root, textvariable=self.selected_user, state="readonly"); self.user_dropdown.pack(pady=5, padx=20, fill='x')
        button_frame = tk.Frame(root); button_frame.pack(pady=10)
        tk.Button(button_frame, text="뒤로", command=self.go_back).pack(side="left", padx=5)
        tk.Button(button_frame, text="시작", command=self.start_main_app).pack(side="left", padx=5)
        self.fetch_users()
    def fetch_users(self):
        try:
            response = requests.get(f"{API_BASE_URL}/api/users"); response.raise_for_status()
            user_ids = response.json().get('user_ids', [])
            if user_ids: self.user_dropdown['values'] = user_ids; self.selected_user.set(user_ids[0])
            else: self.user_dropdown['values'] = []; self.selected_user.set("생성된 사용자 없음")
        except Exception as e: print(f"🚨 사용자 목록 로드 실패: {e}"); self.selected_user.set("로드 실패")
    def start_main_app(self):
        user_id = self.selected_user.get()
        if not user_id or user_id in ["생성된 사용자 없음", "로드 실패"]: return
        self.root.destroy(); main_hub_root = tk.Tk(); MainHubWindow(main_hub_root, user_id); main_hub_root.mainloop()
    def go_back(self): self.root.destroy(); run_app()
    
class MainHubWindow:
    def __init__(self, root, user_id):
        self.root = root; self.root.title(f"메인 메뉴 - {user_id}"); center_window(self.root, 300, 250); self.user_id = user_id
        tk.Label(root, text=f"{user_id}님, 환영합니다!", font=("Helvetica", 12)).pack(pady=10)
        tk.Label(root, text="작업을 선택해주세요", font=("Helvetica", 14)).pack(pady=5)
        button_frame = tk.Frame(root); button_frame.pack(pady=10)
        tk.Button(button_frame, text="트렌드 정보 보기", command=self.open_trend_view).pack(fill="x", pady=3)
        tk.Button(button_frame, text="맞춤 추천 보기", command=self.open_recommendation_view).pack(fill="x", pady=3)
        tk.Button(button_frame, text="로그아웃", command=self.go_back_to_start).pack(fill="x", pady=3)
    def open_trend_view(self): self.root.destroy(); trend_root = tk.Tk(); TrendViewWindow(trend_root, self.user_id); trend_root.mainloop()
    def open_recommendation_view(self): self.root.destroy(); reco_root = tk.Tk(); BookViewWindow(reco_root, user_id=self.user_id); reco_root.mainloop()
    def go_back_to_start(self): self.root.destroy(); run_app()

class TrendViewWindow:
    def __init__(self, root, user_id):
        self.root = root; self.root.title("최신 트렌드"); center_window(self.root, 600, 800); self.user_id = user_id
        top_frame = tk.Frame(root); top_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(top_frame, text="◀ 메인 메뉴로", command=self.go_back).pack(side="left")
        canvas = tk.Canvas(root); scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        self.load_trends(scrollable_frame)
    def load_trends(self, frame):
        try:
            response = requests.get(f"{API_BASE_URL}/api/trends/latest"); response.raise_for_status()
            self.display_trends(response.json().get('trends', []), frame)
        except Exception as e: tk.Label(frame, text=f"트렌드 로드 실패: {e}", fg="red").pack()
    def display_trends(self, trends, frame):
        if not trends: tk.Label(frame, text="표시할 트렌드가 없습니다.").pack(); return
        for trend in trends:
            keyword = trend.get('keyword', '키워드 없음'); summary = trend.get('summary', '요약 없음')
            trend_frame = tk.Frame(frame, relief="solid", borderwidth=1, padx=5, pady=5); trend_frame.pack(fill="x", pady=5, padx=5)
            label = tk.Label(trend_frame, text=keyword, font=("Helvetica", 12, "bold"), fg="blue", cursor="hand2")
            label.pack(anchor="w"); label.bind("<Button-1>", lambda e, kw=keyword: self.open_book_recommendations(kw))
            summary_label = tk.Label(trend_frame, text=summary, wraplength=550, justify="left"); summary_label.pack(anchor="w")
    def open_book_recommendations(self, keyword):
        self.root.destroy(); reco_root = tk.Tk(); BookViewWindow(reco_root, user_id=self.user_id, initial_keyword=keyword); reco_root.mainloop()
    def go_back(self): self.root.destroy(); main_hub_root = tk.Tk(); MainHubWindow(main_hub_root, self.user_id); main_hub_root.mainloop()

class BookViewWindow:
    def __init__(self, root, user_id, initial_keyword=None, came_from='main_hub'):
        self.root = root; self.user_id = user_id; self.initial_keyword = initial_keyword; self.came_from = came_from
        
        if initial_keyword:
            self.root.title(f"'{initial_keyword}' 관련 도서 추천")
        else:
            self.root.title(f"맞춤 추천 - {user_id}")
        self.root.geometry("500x700")

        self.info_frame = tk.Frame(root); self.info_frame.pack(pady=5, padx=10, fill="x")
        
        # 스크롤 가능한 books_frame은 그대로 유지
        canvas = tk.Canvas(root); scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        self.books_frame = ttk.Frame(canvas)
        self.books_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.books_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10); scrollbar.pack(side="right", fill="y")

        button_control_frame = tk.Frame(self.info_frame); button_control_frame.pack(pady=5)
        
        if initial_keyword:
            # '트렌드 보기'에서 넘어온 경우
            tk.Button(button_control_frame, text="◀ 트렌드 목록으로", command=self.go_back_to_trends).pack(side="left", padx=5)
            tk.Button(button_control_frame, text="🔄 새로고침", command=lambda: self.load_books_for_keyword(self.initial_keyword)).pack(side="left", padx=5)
            self.category_label = tk.Label(self.info_frame, text=f"추천 주제: {initial_keyword}", font=("Helvetica", 14, "bold")); self.category_label.pack()
            self.load_books_for_keyword(initial_keyword)
        else:
            # '맞춤 추천 보기'로 들어온 경우
            self.Browse_playlist = []; self.num_preferred = 0; self.current_topic_index = -1
            
            self.back_button = tk.Button(button_control_frame, text="◀ 이전", command=self.show_previous_topic, state="disabled"); self.back_button.pack(side="left", padx=5)
            
            # [핵심 수정!] '메인 메뉴로' 버튼과 '새로고침' 버튼이 모두 있도록 수정합니다.
            tk.Button(button_control_frame, text="메인 메뉴로", command=self.go_back_to_hub).pack(side="left", padx=5)
            tk.Button(button_control_frame, text="🔄 새로고침", command=self.build_playlist_and_start).pack(side="left", padx=5)
            
            self.next_button = tk.Button(button_control_frame, text="다음 ▶", command=self.show_next_topic, state="disabled"); self.next_button.pack(side="left", padx=5)
            self.category_label = tk.Label(self.info_frame, text="추천 목록 구성 중...", font=("Helvetica", 14, "bold")); self.category_label.pack()
            
            self.build_playlist_and_start()

    def build_playlist_and_start(self):
        """서버에서 선호/트렌드 키워드를 모두 가져와 하나의 '플레이리스트'를 만듭니다."""
        try:
            # 1. 사용자 선호 키워드 가져오기
            print(f"'{self.user_id}'의 프로필 정보를 서버에 요청합니다...")
            profile_res = requests.get(f"{API_BASE_URL}/api/users/{self.user_id}"); profile_res.raise_for_status()
            preferred_keywords = profile_res.json().get('preferred_keywords', [])
            self.num_preferred = len(preferred_keywords)
            
            # 2. 최신 트렌드 키워드 가져오기
            print("최신 트렌드 목록을 서버에 요청합니다...")
            trends_res = requests.get(f"{API_BASE_URL}/api/trends/latest"); trends_res.raise_for_status()
            latest_trends = trends_res.json().get('trends', [])
            
            # 3. 선호 목록에 없는 새로운 트렌드 키워드 추가
            discovery_keywords = [t['keyword'] for t in latest_trends if t.get('keyword') and t['keyword'] not in preferred_keywords]
            
            # 4. 최종 플레이리스트 생성 및 추천 시작
            self.Browse_playlist = preferred_keywords + discovery_keywords
            self.current_topic_index = -1
            print(f"추천 플레이리스트 생성: 선호({self.num_preferred}개), 새로운 트렌드({len(discovery_keywords)}개)")
            self.show_next_topic() # 첫 추천 시작
        except Exception as e: self.display_error(f"추천 목록 구성 실패: {e}")

    def show_next_topic(self):
        """'다음' 버튼 로직: 플레이리스트의 다음 항목으로 이동합니다."""
        if self.current_topic_index < len(self.Browse_playlist) - 1:
            self.current_topic_index += 1
            self._update_display()

    def show_previous_topic(self):
        """'이전' 버튼 로직: 플레이리스트의 이전 항목으로 이동합니다."""
        if self.current_topic_index > 0:
            self.current_topic_index -= 1
            self._update_display()

    def _update_display(self):
        """현재 인덱스에 해당하는 토픽의 추천을 표시하고 버튼 상태를 업데이트합니다."""
        if 0 <= self.current_topic_index < len(self.Browse_playlist):
            keyword = self.Browse_playlist[self.current_topic_index]
            
            # 현재 토픽이 선호 주제인지, 새로운 트렌드인지 구분하여 표시
            if self.current_topic_index < self.num_preferred:
                self.category_label.config(text=f"선호 주제: {keyword}")
            else:
                self.category_label.config(text=f"새로운 트렌드: {keyword}")
            self.load_books_for_keyword(keyword)
        else:
            # 플레이리스트의 끝에 도달했거나 비어있는 경우
            self.category_label.config(text="모든 추천을 다 보셨습니다!")
            self.display_books([])
        
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        """'이전', '다음' 버튼의 활성화 상태를 업데이트합니다."""
        if hasattr(self, 'back_button'):
            self.back_button.config(state="normal" if self.current_topic_index > 0 else "disabled")
        if hasattr(self, 'next_button'):
            # [핵심 수정!] 전체 플레이리스트의 끝에 도달했는지 여부로 판단합니다.
            self.next_button.config(state="normal" if self.current_topic_index < len(self.Browse_playlist) - 1 else "disabled")

    def send_feedback(self, book_info, rating):
        """서버에 피드백을 보내고, 성공 시 플레이리스트를 다시 만듭니다."""
        keyword = book_info.get('keyword');
        if not keyword or not self.user_id: return
        feedback_data = {"user_id": self.user_id, "book_id": book_info.get('doc_id'), "rating": rating, "keyword": keyword}
        try:
            response = requests.post(f"{API_BASE_URL}/api/feedback", json=feedback_data); response.raise_for_status()
            print("✅ 피드백 성공! 전체 추천 목록을 새로고침합니다.")
            if self.initial_keyword:
                self.load_books_for_keyword(self.initial_keyword)
            else:
                self.build_playlist_and_start() # 피드백 후, 플레이리스트부터 다시 만듭니다.
        except Exception as e: print(f"🚨 피드백 오류: {e}")
        
    # --- 나머지 헬퍼 함수들 (변경 없음) ---
    def go_back_to_trends(self): self.root.destroy(); trend_root = tk.Tk(); TrendViewWindow(trend_root, self.user_id); trend_root.mainloop()
    def go_back_to_hub(self): self.root.destroy(); main_hub_root = tk.Tk(); MainHubWindow(main_hub_root, self.user_id); main_hub_root.mainloop()
    def load_books_for_keyword(self, keyword):
        try:
            user_id_param = self.user_id or "guest"
            response = requests.get(f"{API_BASE_URL}/api/books/by_keyword/{user_id_param}?keyword={keyword}&max_books=5")
            response.raise_for_status(); self.display_books(response.json().get('books', []))
        except Exception as e: self.display_error(f"'{keyword}' 추천 요청 실패: {e}")
    def display_books(self, books):
        for widget in self.books_frame.winfo_children(): widget.destroy()
        if not books: tk.Label(self.books_frame, text="추천할 도서가 없습니다.").pack(); return
        for book in books:
            display_text = f"📖 {book.get('title', '제목 없음')}\n - {book.get('author', '저자 미상')}"
            button = tk.Button(self.books_frame, text=display_text, justify="center", wraplength=450, command=lambda b=book: self.open_feedback_dialog(b))
            button.pack(fill="x", pady=3)
    def open_feedback_dialog(self, book_info):
        if not self.user_id: messagebox.showinfo("알림", "로그인된 사용자만 피드백을 남길 수 있습니다."); return
        dialog = FeedbackDialog(self.root, book_info); self.root.wait_window(dialog)
        if dialog.result_rating is not None: self.send_feedback(book_info, dialog.result_rating)
    def display_error(self, message):
        for widget in self.books_frame.winfo_children(): widget.destroy(); tk.Label(self.books_frame, text=message, font=("Helvetica", 12), fg="red").pack()

if __name__ == "__main__":
    run_app()