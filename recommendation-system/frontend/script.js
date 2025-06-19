document.addEventListener('DOMContentLoaded', () => {
    // --- 기본 설정 및 DOM 요소 가져오기 ---
    const API_BASE_URL = "http://localhost:5001";
    const apiStatusIndicator = document.getElementById('api-status-indicator');

    const userSelectBtn = document.getElementById('user-select-btn')
    const userSelectList = document.getElementById('user-select-list')

    const trendsList = document.getElementById('trends-list');
    const recsList = document.getElementById('recs-list');
    const recsTitle = document.getElementById('recs-title');
    const trendsTabBtn = document.getElementById('trends-tab');
    const recsTabBtn = document.getElementById('recs-tab');
    const recsPagination = document.getElementById('recs-pagination')
    const loadRecsBtn = document.getElementById('load-profile-btn');
    const bookModalEl = document.getElementById('bookRecommenderModal');
    const bookModal = new bootstrap.Modal(bookModalEl);

    const newUserModalEl = document.getElementById('newUserModal')
    const newUserModal = new bootstrap.Modal(newUserModalEl)

    const bookModalLabel = document.getElementById('bookRecommenderModalLabel');
    const bookModalBody = document.getElementById('bookRecommenderModalBody');
    const modalPagination = document.getElementById('modal-pagination')
    const prevTopicBtn = document.getElementById('prev-topic-btn');
    const nextTopicBtn = document.getElementById('next-topic-btn');
    const saveUserBtn = document.getElementById('save-user-btn');

    const firstTopicBtn = document.getElementById('first-topic-btn')

    const trendDateDisplay = document.getElementById('trend-date-display');
    const prevTrendBtn = document.getElementById('prev-trend-btn');
    const nextTrendBtn = document.getElementById('next-trend-btn');

    // --- 상태 관리 변수 ---
    let currentUserId = null;
    let BrowsePlaylist = [];
    let currentTopicIndex = -1;
    let numPreferred = 0;

    let trendDates = [];
    let currentTrendIndex = 0;

    // --- API 헬퍼 함수 ---
    async function fetchApi(url, options = {}) {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: '서버 응답 오류' }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    function renderPagination(container, totalBooks, pageSize, currentPage, onPageClick) {
        container.innerHTML = '';
        if (totalBooks <= pageSize) return;

        const totalPages = Math.ceil(totalBooks / pageSize);
        const nav = document.createElement('nav');
        const ul = document.createElement('ul');
        ul.className = 'pagination';

        for (let i = 1; i <= totalPages; i++) {
            const li = document.createElement('li');
            li.className = 'page-item';
            if (i === currentPage) {
                li.classList.add('active');
            }
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = i;
            a.dataset.page = i;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                onPageClick(i);
            });
            li.appendChild(a);
            ul.appendChild(li);
        }
        nav.appendChild(ul);
        container.appendChild(nav);
    }
    
    // --- [신규] 특정 토픽의 책 목록과 페이지네이션을 불러오는 함수 ---
    async function loadAndDisplayBooks(keyword, page, container, paginationContainer) {
        container.innerHTML = `<div class="text-center p-3"><div class="spinner-border spinner-border-sm"></div></div>`;
        paginationContainer.innerHTML = '';

        try {
            const data = await fetchApi(`${API_BASE_URL}/api/books/by_keyword/${currentUserId}?keyword=${encodeURIComponent(keyword)}&page=${page}&page_size=5`);
            displayBooks(data.books || [], container, true);
            renderPagination(paginationContainer, data.total_books, 5, page, (newPage) => {
                loadAndDisplayBooks(keyword, newPage, container, paginationContainer);
            });
        } catch (error) {
            container.innerHTML = `<div class="alert alert-danger">도서 로드 실패: ${error.message}</div>`;
        }
    }

    // --- 초기화 및 UI 업데이트 함수들 ---
    async function checkApiStatus() {
        try {
            await fetchApi(API_BASE_URL);
            apiStatusIndicator.textContent = '✅ API 연결됨';
            apiStatusIndicator.classList.remove('bg-secondary', 'bg-danger');
            apiStatusIndicator.classList.add('bg-success');
        } catch (error) {
            apiStatusIndicator.textContent = '❌ API 연결 실패';
            apiStatusIndicator.classList.remove('bg-secondary', 'bg-success');
            apiStatusIndicator.classList.add('bg-danger');
        }
    }

    async function loadUsers() {
        try {
            const data = await fetchApi(`${API_BASE_URL}/api/users`);
            const userIds = data.user_ids || [];
            userSelectList.innerHTML = '';

            userIds.forEach(userId => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.className = 'dropdown-item';
                a.href = '#';
                a.textContent = userId;
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    // 아이템 클릭 시 메인 버튼의 텍스트를 바꾸고, 선택된 값을 저장합니다.
                    userSelectBtn.textContent = userId;
                    userSelectBtn.dataset.selectedUser = userId;
                });
                li.appendChild(a);
                userSelectList.appendChild(li);
            });
        } catch (error) { console.error('사용자 목록 로드 실패:', error); }
    }
    
    function formatTrendDate(dateStr) {
        if (!dateStr || dateStr.length !== 6) return '';
        const year = dateStr.substring(0, 2);
        const month = dateStr.substring(2, 4);
        const day = dateStr.substring(4, 6);
        return `(${year}년 ${month}월 ${day}일)`;
    }

    // 트렌드 탐색 버튼의 활성화/비활성화 상태를 업데이트하는 함수
    function updateTrendNavButtons() {
        nextTrendBtn.disabled = currentTrendIndex <= 0;
        prevTrendBtn.disabled = currentTrendIndex >= trendDates.length - 1;
    }

    // 특정 날짜의 트렌드 데이터를 불러와 화면에 표시하는 함수
    async function fetchAndDisplayTrendByDate(dateId) {
        // 로딩 스피너를 먼저 표시
        trendsList.innerHTML = `<div class="text-center p-5"><div class="spinner-border" role="status"></div></div>`;
        
        // 날짜 표시 및 버튼 상태 업데이트
        trendDateDisplay.textContent = formatTrendDate(dateId);
        updateTrendNavButtons();

        try {
            const data = await fetchApi(`${API_BASE_URL}/api/trends/by_date/${dateId}`);
            const trends = data.trends || [];
            trendsList.innerHTML = ''; // 이전 목록 지우기

            if (trends.length === 0) {
                trendsList.innerHTML = '<p class="text-center text-muted p-5">표시할 트렌드가 없습니다.</p>';
                return;
            }

            trends.forEach(trend => {
                const trendItem = document.createElement('a');
                trendItem.className = 'list-group-item list-group-item-action flex-column align-items-start';
                trendItem.href = "#";
                trendItem.innerHTML = `<h5 class="mb-1">${trend.keyword}</h5><p class="mb-1">${trend.summary || ''}</p>`;
                trendItem.addEventListener('click', (e) => { e.preventDefault(); handleTrendClick(trend.keyword); });
                trendsList.appendChild(trendItem);
            });
        } catch(error) {
            trendsList.innerHTML = `<div class="alert alert-danger">트렌드 로드 실패: ${error.message}</div>`;
        }
    }

    async function loadTrends() {
        // 다른 탭에 갔다가 돌아올 때도 화면을 다시 그려주기 위해 if문을 수정합니다.
        if (trendDates.length === 0) {
            // 맨 처음 로드할 때만 날짜 목록을 가져옵니다.
            // 버튼을 미리 비활성화하여 잘못된 클릭을 방지합니다.
            prevTrendBtn.disabled = true;
            nextTrendBtn.disabled = true;

            try {
                const data = await fetchApi(`${API_BASE_URL}/api/trends/dates`);
                trendDates = data.dates || [];

                if (trendDates.length > 0) {
                    currentTrendIndex = 0;
                    // 날짜 목록을 성공적으로 가져온 후, 첫 번째 트렌드를 화면에 표시합니다.
                    await fetchAndDisplayTrendByDate(trendDates[currentTrendIndex]);
                } else {
                    trendsList.innerHTML = '<p class="text-center text-muted p-5">표시할 트렌드가 없습니다.</p>';
                }
            } catch (error) {
                trendsList.innerHTML = `<div class="alert alert-danger">트렌드 날짜 목록 로드 실패: ${error.message}</div>`;
            }
        } else {
            // 이미 날짜 목록이 있다면, 현재 인덱스의 트렌드를 다시 보여주기만 합니다.
            await fetchAndDisplayTrendByDate(trendDates[currentTrendIndex]);
        }
    }

    
    
    // --- 맞춤 추천 핵심 로직 ---
    async function startPersonalizedRecommendations() {
        recsTitle.textContent = `'${currentUserId}'님 맞춤 추천 구성 중...`;
        recsList.innerHTML = `<div class.py="text-center p-5"><div class="spinner-border" role="status"></div></div>`;
        updateNavButtons(); // 버튼 초기화

        try {
            const profilePromise = fetchApi(`${API_BASE_URL}/api/users/${currentUserId}`);
            const trendsPromise = fetchApi(`${API_BASE_URL}/api/trends/latest`);
            
            const [profile, trendsData] = await Promise.all([profilePromise, trendsPromise]);
            
            const keyword_scores = profile.keyword_scores || {};
            const preferredKeywords = Object.keys(keyword_scores).filter(key => keyword_scores[key] >= 3)
            numPreferred = preferredKeywords.length;
            const latestTrends = trendsData.trends || [];
            
            const discoveryKeywords = latestTrends
                .map(t => t.keyword)
                .filter(k => k && !preferredKeywords.includes(k));
            
            BrowsePlaylist = [...preferredKeywords, ...discoveryKeywords];
            currentTopicIndex = -1;
            console.log(`추천 플레이리스트 생성: 선호(${numPreferred}개), 새로운 트렌드(${discoveryKeywords.length}개)`);
            
            showNextTopic();
        } catch(error) {
            recsList.innerHTML = `<div class="alert alert-danger">맞춤 추천 로드 실패: ${error.message}</div>`;
        }
    }

    function showNextTopic() {
        if (currentTopicIndex < BrowsePlaylist.length - 1) {
            currentTopicIndex++;
            updateRecsDisplay();
        }
    }

    function showPrevTopic() {
        if (currentTopicIndex > 0) {
            currentTopicIndex--;
            updateRecsDisplay();
        }
    }

    function showFirstTopic() {
        // 이미 첫번째가 아닐 경우에만 동작
        if (currentTopicIndex > 0) {
            currentTopicIndex = 0; // 인덱스를 0으로 리셋
            updateRecsDisplay(); // 화면 업데이트
        }
    }

    async function updateRecsDisplay() {
        updateNavButtons();
        if (currentTopicIndex < 0 || currentTopicIndex >= BrowsePlaylist.length) {
            recsTitle.textContent = '모든 추천을 보셨습니다!';
            recsList.innerHTML = '';
            recsPagination.innerHTML = ''; // [추가]
            return;
        }
        
        const keyword = BrowsePlaylist[currentTopicIndex];
        const titlePrefix = currentTopicIndex < numPreferred ? '선호 주제' : '새로운 트렌드';
        recsTitle.textContent = `${titlePrefix}: ${keyword}`;
        
        // [수정!] loadAndDisplayBooks 함수 호출
        loadAndDisplayBooks(keyword, 1, recsList, recsPagination);
    }
    
    function updateNavButtons() {
        prevTopicBtn.disabled = currentTopicIndex <= 0;
        nextTopicBtn.disabled = currentTopicIndex >= BrowsePlaylist.length - 1;
    }

    // --- 공용 및 팝업창 관련 함수 ---
    async function handleTrendClick(keyword) {
        if (!currentUserId) {
            alert('피드백을 남기려면 먼저 "사용자 설정" 탭에서 사용자를 선택해주세요.'); return;
        }
        bookModalLabel.textContent = `'${keyword}' 관련 추천 도서`;
        bookModal.show();
        
        // [수정!] loadAndDisplayBooks 함수 호출
        loadAndDisplayBooks(keyword, 1, bookModalBody, modalPagination);
    }
    
    function displayBooks(books, container, allowFeedback) {
        // 이 함수는 이전 버전과 거의 동일 (페이지네이션 관련 로직 없음)
        container.innerHTML = '';
        if (books.length === 0) { container.innerHTML = '<p class="text-center text-muted">추천할 도서가 없습니다.</p>'; return; }
        
        const bookListGroup = document.createElement('div');
        bookListGroup.className = 'list-group';
        
        books.forEach(book => {
            const bookEl = document.createElement('a');
            bookEl.className = 'list-group-item list-group-item-action';
            bookEl.href = "#";
            bookEl.setAttribute('data-book-id', book.doc_id);
            bookEl.setAttribute('data-keyword', book.keyword);
            bookEl.setAttribute('data-book-title', book.title);
            if (allowFeedback) {
                bookEl.setAttribute('data-feedback-enabled', 'true');
            }

            let titleHtml;
            const originalTitle = book.title || '제목 없음';

            if (originalTitle.includes(' = ')) {
                // ' = '를 기준으로 한글과 영어 제목을 분리합니다.
                const parts = originalTitle.split(' = ', 2);
                const koreanTitle = parts[0].trim();
                const englishTitle = parts[1].trim();
                // 한글 제목, 줄바꿈(<br>), 그리고 작은 회색 글씨의 영어 제목으로 구성합니다.
                titleHtml = `<h6>${koreanTitle}<br><small class="text-secondary">${englishTitle}</small></h6>`;
            } else {
                // ' = '가 없는 제목은 그대로 표시합니다.
                titleHtml = `<h6>${originalTitle}</h6>`;
            }
            // -----------------------------------------

            const authorHtml = `<small class="text-muted">${book.author || '저자 미상'}</small>`;

            bookEl.innerHTML = `${titleHtml}${authorHtml}`;
            bookListGroup.appendChild(bookEl);
        });
        container.appendChild(bookListGroup);
    }
    
    // --- 이벤트 리스너 설정 ---
    loadRecsBtn.addEventListener('click', async () => {
        const selectedUser = userSelectBtn.dataset.selectedUser
        if (!selectedUser || selectedUser === "") {
            alert('먼저 사용자를 선택해주세요.');
            return;
        }

        // 앱 전체에서 사용할 현재 사용자 ID를 설정합니다.
        currentUserId = selectedUser;

        try {
            // API를 호출하여 사용자 이름을 가져옵니다.
            const profile = await fetchApi(`${API_BASE_URL}/api/users/${currentUserId}`);
            // profile.name이 없는 경우를 대비해 ID를 대신 사용합니다.
            const userName = profile.name || currentUserId; 

            // 성공 팝업창을 띄웁니다.
            alert(`${userName} 프로필이 로드되었습니다.`);

        } catch (error) {
            alert(`프로필 로드에 실패했습니다: ${error.message}`);
            currentUserId = null; // 실패 시 사용자 선택을 초기화합니다.
        }
    });

    // [추가!] 트렌드 탐색 버튼 이벤트 리스너
    prevTrendBtn.addEventListener('click', () => {
        if (currentTrendIndex < trendDates.length - 1) {
            currentTrendIndex++;
            fetchAndDisplayTrendByDate(trendDates[currentTrendIndex]);
        }
    });

    nextTrendBtn.addEventListener('click', () => {
        if (currentTrendIndex > 0) {
            currentTrendIndex--;
            fetchAndDisplayTrendByDate(trendDates[currentTrendIndex]);
        }
    });

    trendsTabBtn.addEventListener('shown.bs.tab', loadTrends);
    recsTabBtn.addEventListener('shown.bs.tab', () => {
        if (!currentUserId) {
            alert('먼저 "사용자 설정" 탭에서 사용자를 선택하고 "맞춤 추천 보기" 버튼을 눌러주세요.');
            const userTab = new bootstrap.Tab(document.getElementById('user-tab'));
            userTab.show();
            return;
        }
        startPersonalizedRecommendations();
    });
    
    prevTopicBtn.addEventListener('click', showPrevTopic);
    nextTopicBtn.addEventListener('click', showNextTopic);

    firstTopicBtn.addEventListener('click', showFirstTopic)

    saveUserBtn.addEventListener('click', async () => {
        // 1. 입력 필드에서 값 가져오기
        const userId = document.getElementById('new-user-id').value.trim();
        const userName = document.getElementById('new-user-name').value.trim();
        const userAge = document.getElementById('new-user-age').value.trim();
        const userFreq = document.getElementById('new-user-freq').value.trim();

        const keywordsArray = document.getElementById('new-user-keywords').value.split(',')
            .map(k => k.trim())
            .filter(k => k); // 빈 문자열 제거

        // 2. 필수 값 확인
        if (!userId || !userName) {
            alert('사용자 ID와 이름은 필수 항목입니다.');
            return;
        }

        // 3. 키워드 배열을 {키워드: 3} 형태의 객체(맵)로 변환합니다.
        const keywordScoresObject = keywordsArray.reduce((acc, keyword) => {
            if (keyword) { // 혹시 모를 빈 키워드는 제외
                acc[keyword] = 3; // 각 키워드에 기본 점수 3점 할당
            }
            return acc;
        }, {});

        // 4. 서버에 보낼 데이터 객체에서 preferred_keywords를 없애고 keyword_scores를 사용합니다.
        const newUserProfile = {
            user_id: userId,
            name: userName,
            age_group: userAge,
            reading_frequency: userFreq,
            keyword_scores: keywordScoresObject // 새로 만든 객체를 할당
        };

        try {
            // 5. API 호출하여 사용자 생성
            const response = await fetchApi(`${API_BASE_URL}/api/users`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newUserProfile)
            });

            alert(`사용자 '${response.user.name}' 생성이 완료되었습니다.`);
            
            // 5. 성공 시 모달 닫고, 사용자 목록 새로고침
            newUserModal.hide();
            document.getElementById('new-user-form').reset(); // 폼 초기화
            await loadUsers(); // 사용자 목록 다시 불러오기
            userSelectBtn.textContent = userId; // 버튼 텍스트를 새 사용자 ID로 변경
            userSelectBtn.dataset.selectedUser = userId; // 선택된 값도 변경

        } catch (error) {
            alert(`사용자 생성 실패: ${error.message}`);
        } 
    });

    // --- [수정] 피드백 모달 관련 로직 (울타리 안으로 이동) ---
    const feedbackModalEl = document.getElementById('feedbackModal');
    const feedbackModal = new bootstrap.Modal(feedbackModalEl);
    const feedbackBookTitle = document.getElementById('feedback-book-title');
    const starRatingContainer = feedbackModalEl.querySelector('.star-rating');
    const stars = starRatingContainer.querySelectorAll('span');
    const submitFeedbackBtn = document.getElementById('submit-feedback-btn');

    let selectedRating = 0;
    let currentFeedbackInfo = {};

    // 별 표시를 업데이트하는 헬퍼 함수
    function renderStars(ratingToDisplay) {
        stars.forEach(star => {
            const starValue = parseInt(star.dataset.value);
            if (starValue <= ratingToDisplay) {
                star.innerHTML = '★'; // 꽉 찬 별
                star.classList.add('selected');
            } else {
                star.innerHTML = '☆'; // 빈 별
                star.classList.remove('selected');
            }
        });
    }

    // 별점 UI 상호작용 처리
    stars.forEach(star => {
        // 마우스를 올렸을 때: 임시로 별을 채워서 보여줌
        star.addEventListener('mouseover', () => {
            renderStars(parseInt(star.dataset.value));
        });

        // 마우스를 뗐을 때: 원래 선택했던 별점으로 되돌림
        star.addEventListener('mouseout', () => {
            renderStars(selectedRating);
        });

        // 클릭했을 때: 새로운 별점을 확정
        star.addEventListener('click', () => {
            selectedRating = parseInt(star.dataset.value);
            renderStars(selectedRating);
        });
    });


    function handleBookClick(event) {
        const bookEl = event.target.closest('a.list-group-item[data-feedback-enabled="true"]');
        if (!bookEl) return;

        event.preventDefault();
        
        if (!currentUserId) {
            alert('피드백을 남기려면 먼저 "사용자 설정" 탭에서 사용자를 선택해주세요.');
            return;
        }

        currentFeedbackInfo = {
            bookId: bookEl.dataset.bookId,
            keyword: bookEl.dataset.keyword,
            title: bookEl.dataset.bookTitle
        };

        let titleForModal = currentFeedbackInfo.title || '제목 없음';
        if (titleForModal.includes(' = ')) {
            // ' = '가 있으면 그 앞부분(한글 제목)만 사용합니다.
            titleForModal = titleForModal.split(' = ')[0].trim();
        }

        feedbackBookTitle.textContent = titleForModal
        selectedRating = 0;
        stars.forEach(s => s.classList.remove('selected'));
        feedbackModal.show();
    }

    recsList.addEventListener('click', handleBookClick);
    bookModalBody.addEventListener('click', handleBookClick);

    submitFeedbackBtn.addEventListener('click', async () => {
        if (selectedRating === 0) {
            alert('별점을 선택해주세요.');
            return;
        }

        try {
            const feedbackData = {
                user_id: currentUserId,
                book_id: currentFeedbackInfo.bookId,
                rating: selectedRating,
                keyword: currentFeedbackInfo.keyword
            };

            await fetchApi(`${API_BASE_URL}/api/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(feedbackData)
            });
            
            feedbackModal.hide();
            
            if (recsTabBtn.classList.contains('active')) {
                startPersonalizedRecommendations();
            }

        } catch (error) {
            alert(`피드백 제출 실패: ${error.message}`);
        }
    });

    // --- 페이지 로드 시 초기화 ---
    checkApiStatus().then(loadUsers);
});