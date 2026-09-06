/** App - Bảng Niêm Yết TTHC UBND xã Vĩnh Bảo
 *  Dashboard · danh sách thẻ · chi tiết TTHC · link DVC
 */
(async function () {
  const config = window.TTHC_CONFIG || {};
  let raw = window.TTHC_DATA || null;
  let dataSourceStatus = "Dữ liệu cục bộ phục hồi từ workspace; đang tiếp tục đối chiếu nguồn chính thức.";

  function mergeRemotePayload(payload) {
    if (Array.isArray(payload)) return { ...(raw || {}), thuTuc: payload };
    if (payload && Array.isArray(payload.thuTuc)) return { ...(raw || {}), ...payload };
    return null;
  }

  async function loadConfiguredJson() {
    const url = String(config.remoteJsonUrl || "").trim();
    if (!url) return null;
    const cacheKey = String(config.cacheKey || "tthc_vinhbao_v2");
    const maxAgeMs = Math.max(1, Number(config.refreshHours) || 12) * 60 * 60 * 1000;

    try {
      const cached = JSON.parse(localStorage.getItem(cacheKey) || "null");
      if (cached?.savedAt && Date.now() - cached.savedAt < maxAgeMs) {
        const merged = mergeRemotePayload(cached.payload);
        if (merged) {
          dataSourceStatus = "Dữ liệu đồng bộ từ bộ nhớ đệm: " + url;
          return merged;
        }
      }
    } catch (_) {}

    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const payload = await response.json();
      const merged = mergeRemotePayload(payload);
      if (!merged) throw new Error("Sai cấu trúc dữ liệu");
      try {
        localStorage.setItem(cacheKey, JSON.stringify({ savedAt: Date.now(), payload }));
      } catch (_) {}
      dataSourceStatus = "Đã đồng bộ dữ liệu JSON: " + url;
      return merged;
    } catch (_) {
      return null;
    }
  }

  if (config.autoSyncOnLoad !== false) {
    const remote = await loadConfiguredJson();
    if (remote) raw = remote;
  }
  if (!raw) return;

  const LOGO = "assets/logo-hcc.png";
  // Cổng DVCQG – link trực tiếp chỉ tạo khi đã có formalityId.
  const DVC_HOME = "https://dichvucong.gov.vn";
  const DVC_TTHC_HOME = "https://dichvucong.gov.vn/thu-tuc-hanh-chinh";
  const DVC_DETAIL_BY_ID = "https://dichvucong.gov.vn/thu-tuc-hanh-chinh/";
  const DVC_SUBMIT_SEARCH = "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh";
  const HP_PROVINCE_ID = "019bad30-cd83-76ea-9f9a-bc6cebad4138";
  const VINHBAO_WARD_ID = "019bad30-cd84-7750-aaa5-8100fc7ceef8";
  const DVC_HP = "https://dichvucong.haiphong.gov.vn";
  const CHUA_XAC_MINH = "Chưa xác minh";
  const KNOWN_FORMALITY_IDS = {
    "2.000942": "019d2bfd-95d6-778f-889b-e3045003fa5e"
  };

  const NGANH_MAP = [
    { key: /hộ tịch|khai sinh|khai tử|kết hôn|giám hộ|nuôi con/i, nganh: "Tư pháp" },
    { key: /đất đai|nhà ở|xây dựng|quy hoạch/i, nganh: "Tài nguyên & Xây dựng" },
    { key: /bảo hiểm|lao động|việc làm|người có công|xã hội/i, nganh: "LĐ-TB&XH" },
    { key: /y tế|bảo vệ sức khỏe|dược/i, nganh: "Y tế" },
    { key: /giáo dục|học sinh|trường/i, nganh: "Giáo dục" },
    { key: /nông nghiệp|thủy sản|chăn nuôi|thú y|lâm nghiệp|trồng trọt/i, nganh: "Nông nghiệp" },
    { key: /môi trường|khoáng sản/i, nganh: "Tài nguyên & Môi trường" },
    { key: /văn hóa|thể thao|du lịch|thông tin/i, nganh: "VH-TT" },
    { key: /tài chính|ngân sách|phí|lệ phí/i, nganh: "Tài chính" },
    { key: /công an|an ninh|trật tự|cư trú|căn cước/i, nganh: "Công an" },
    { key: /kinh tế|doanh nghiệp|hợp tác xã|đầu tư/i, nganh: "Kinh tế" }
  ];

  function guessNganh(tt) {
    if (tt.nganh) return tt.nganh;
    const s = (tt.linhVuc || "") + " " + (tt.ten || "");
    for (const m of NGANH_MAP) if (m.key.test(s)) return m.nganh;
    return "UBND xã";
  }

  function normalizeMa(ma) {
    return String(ma || "")
      .replace(/\.H24$/i, "")
      .replace(/\.000\.00\.00$/i, "")
      .replace(/\s+/g, "")
      .trim();
  }

  /** Mã ngắn ổn định trên Cổng DVC: lấy 2 phần đầu (1.001193) */
  function shortMa(ma) {
    let m = String(ma || "")
      .trim()
      .replace(/\s+/g, "")
      .replace(/\.H\d{2}$/i, "");
    if (!m) return "";
    const hit = m.match(/^(\d+\.\d+)/);
    return hit ? hit[1] : m;
  }

  function resolveFormalityId(tt) {
    const direct = String(tt?.formalityId || "").trim();
    if (direct) return direct;
    return KNOWN_FORMALITY_IDS[shortMa(tt?.ma)] || "";
  }

  function dvcDetailUrlById(formalityId) {
    return formalityId ? DVC_DETAIL_BY_ID + encodeURIComponent(formalityId) : "";
  }

  /** Fallback khi chưa có formalityId: tìm theo tên trên miền chính thức. */
  function dvcSearchByName(ten) {
    const q = (ten || "").trim();
    if (!q) return DVC_TTHC_HOME;
    return "https://www.google.com/search?q=" + encodeURIComponent('"' + q + '" site:dichvucong.gov.vn');
  }

  function dvcSubmitUrl(formalityId) {
    if (!formalityId) return DVC_TTHC_HOME;
    const params = new URLSearchParams({
      formalityId,
      province: HP_PROVINCE_ID,
      ministry: "",
      ward: VINHBAO_WARD_ID,
      searchType: "PROVINCE",
      commune: "WARD",
      provinceCode: "31",
      wardCode: "11824"
    });
    return DVC_SUBMIT_SEARCH + "?" + params.toString();
  }

  function enrich(tt) {
    const ma = normalizeMa(tt.ma) || tt.ma || "";
    const nganh = guessNganh(tt);
    const formalityId = resolveFormalityId(tt);
    const dvcTraCuu = dvcSearchByName(tt.ten);
    return {
      ...tt,
      ma,
      nganh,
      formalityId,
      cap: tt.cap || CHUA_XAC_MINH,
      dvctt: tt.dvctt || CHUA_XAC_MINH,
      phi: tt.phi || CHUA_XAC_MINH,
      quyetDinh: tt.quyetDinh || CHUA_XAC_MINH,
      thoiHan: tt.thoiHan || CHUA_XAC_MINH,
      coQuan: tt.coQuan || CHUA_XAC_MINH,
      dvcLink: tt.dvcLink || dvcDetailUrlById(formalityId) || dvcTraCuu,
      dvcNop: tt.dvcNop || dvcSubmitUrl(formalityId),
      dvcTraCuu,
      dvcTthcHome: DVC_TTHC_HOME,
      dvcHp: DVC_HP,
      maNgan: shortMa(tt.ma),
      quyTrinh: Array.isArray(tt.quyTrinh) ? tt.quyTrinh : [],
      thanhPhan: Array.isArray(tt.thanhPhan) ? tt.thanhPhan : [],
      daXacMinh: Boolean(tt.daXacMinh)
    };
  }

  function dedupeThuTuc(list) {
    const map = new Map();
    list.forEach((tt) => {
      const key = normalizeMa(tt.ma) || ("ten:" + (tt.ten || "").toLowerCase().trim());
      if (!key) return;
      const prev = map.get(key);
      if (!prev) {
        map.set(key, enrich(tt));
        return;
      }
      if (tt.nhanh && !prev.nhanh) map.set(key, enrich({ ...tt, nhanh: true }));
      else if ((tt.ten || "").length > (prev.ten || "").length)
        map.set(key, enrich({ ...tt, nhanh: prev.nhanh || tt.nhanh }));
    });
    return Array.from(map.values())
      .sort(
        (a, b) =>
          (a.linhVuc || "").localeCompare(b.linhVuc || "", "vi") ||
          (a.ten || "").localeCompare(b.ten || "", "vi")
      )
      .map((tt, i) => ({ ...tt, stt: i + 1, _id: "tt-" + i }));
  }

  function buildLinhVuc(thuTucList, rawLv) {
    const counts = {};
    thuTucList.forEach((tt) => {
      const k = (tt.linhVuc || "").trim();
      if (k) counts[k] = (counts[k] || 0) + 1;
    });
    const fromData = Object.keys(counts).sort((a, b) => a.localeCompare(b, "vi"));
    const idMap = {};
    (rawLv || []).forEach((lv) => {
      if (lv.ten) idMap[lv.ten] = lv.id;
    });
    return fromData.map((ten, i) => ({
      id: idMap[ten] || "lv-auto-" + (i + 1),
      ten,
      soThuTuc: counts[ten]
    }));
  }

  const thuTucAll = dedupeThuTuc(raw.thuTuc || []);
  const linhVucAll = buildLinhVuc(thuTucAll, raw.linhVuc || []);
  const data = { ...raw, thuTuc: thuTucAll, linhVuc: linhVucAll };
  window.TTHC_DATA_CLEAN = data;
  const byId = Object.fromEntries(data.thuTuc.map((t) => [t._id, t]));

  // DOM
  const grid = document.getElementById("linhVucGrid");
  const linhVucCount = document.getElementById("linhVucCount");
  const thuTucList = document.getElementById("thuTucList");
  const thuTucCount = document.getElementById("thuTucCount");
  const thuTucTitle = document.getElementById("thuTucTitle");
  const searchInput = document.getElementById("searchInput");
  const btnClearSearch = document.getElementById("btnClearSearch");
  const searchResultCount = document.getElementById("searchResultCount");
  const activeFilters = document.getElementById("activeFilters");
  const filterLinhVuc = document.getElementById("filterLinhVuc");
  const filterNhanh = document.getElementById("filterNhanh");
  const filterMienPhi = document.getElementById("filterMienPhi");
  const filterPdg = document.getElementById("filterPdg");
  const footerSync = document.getElementById("footerSync");
  const btnTop = document.getElementById("btnTop");
  const navBtns = document.querySelectorAll(".nav-btn");
  const panels = document.querySelectorAll(".tab-panel");
  const btnClearFilter = document.getElementById("btnClearFilter");
  const btnBackLv = document.getElementById("btnBackLv");
  const ttFilterWrap = document.getElementById("ttFilterWrap");
  const ttLocalSearch = document.getElementById("ttLocalSearch");
  const dashStats = document.getElementById("dashStats");
  const dashTopLv = document.getElementById("dashTopLv");
  const dashNhanh = document.getElementById("dashNhanh");
  const detailOverlay = document.getElementById("detailOverlay");
  const detailBody = document.getElementById("detailBody");
  const pagination = document.getElementById("pagination");
  const btnPrevPage = document.getElementById("btnPrevPage");
  const btnNextPage = document.getElementById("btnNextPage");
  const pageInfo = document.getElementById("pageInfo");

  const PAGE_SIZE = 30;
  let activeLinhVuc = "";
  let lastList = [];
  let currentPage = 1;

  function countByLinhVuc(ten) {
    return data.thuTuc.filter((tt) => tt.linhVuc === ten).length;
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .replace(/Đ/g, "D")
      .toLowerCase()
      .trim();
  }

  function isTrueFlag(value) {
    if (value === true || value === 1) return true;
    return /^(true|1|yes|co|có)$/i.test(String(value || "").trim());
  }

  function updateFilterUi(resultCount) {
    const keyword = String(searchInput?.value || "").trim();
    if (btnClearSearch) btnClearSearch.hidden = !keyword;
    if (searchResultCount) {
      searchResultCount.hidden = !keyword;
      searchResultCount.textContent = keyword ? resultCount + " kết quả" : "";
    }
    if (activeFilters) {
      const chips = [];
      const lv = String(filterLinhVuc?.value || activeLinhVuc || "").trim();
      if (lv) chips.push("Lĩnh vực: " + lv);
      if (filterNhanh?.checked) chips.push("Trong ngày (T4)");
      if (filterMienPhi?.checked) chips.push("Miễn phí trực tuyến");
      if (filterPdg?.checked) chips.push("Phi địa giới");
      activeFilters.hidden = chips.length === 0;
      activeFilters.innerHTML = chips.map((chip) => `<span class="active-filter-chip">${esc(chip)}</span>`).join("");
    }
  }

  function tagsHtml(tt) {
    const status = tt.daXacMinh
      ? '<span class="tag tag-verified">Đã xác minh</span>'
      : '<span class="tag tag-unverified">Chưa xác minh</span>';
    return `
      <span class="tag tag-ma">Mã: ${esc(tt.ma || "—")}</span>
      ${status}
      <span class="tag tag-dvc">DVCTT: ${esc(tt.dvctt)}</span>
      <span class="tag tag-phi">Phí/lệ phí: ${esc(tt.phi)}</span>
      <span class="tag tag-lv">LV: ${esc(tt.linhVuc)}</span>
      <span class="tag tag-nganh">Ngành: ${esc(tt.nganh)}</span>
      ${tt.nhanh ? '<span class="tag tag-unverified">Giải quyết trong ngày: chưa xác minh</span>' : ""}`;
  }

  function renderDashboard() {
    const total = data.thuTuc.length;
    const lv = data.linhVuc.length;
    const nhanh = data.thuTuc.filter((t) => t.nhanh).length;
    const top = [...data.linhVuc]
      .sort((a, b) => countByLinhVuc(b.ten) - countByLinhVuc(a.ten))
      .slice(0, 8);

    if (dashStats) {
      dashStats.innerHTML = `
        <div class="stat-card"><img src="${LOGO}" alt="" class="stat-logo" /><div class="stat-num">${total}</div><div class="stat-label">Tổng thủ tục</div></div>
        <div class="stat-card"><div class="stat-icon">🗂️</div><div class="stat-num">${lv}</div><div class="stat-label">Lĩnh vực</div></div>
        <div class="stat-card accent"><div class="stat-icon">⚡</div><div class="stat-num">${nhanh}</div><div class="stat-label">Trong ngày (T4)</div></div>
        <div class="stat-card"><div class="stat-icon">🏛️</div><div class="stat-num">Xã</div><div class="stat-label">Cấp giải quyết</div></div>`;
    }
    if (dashTopLv) {
      dashTopLv.innerHTML = top
        .map(
          (item, i) =>
            `<li data-lv="${esc(item.ten)}"><span class="rank">${i + 1}</span><span class="lv-name">${esc(item.ten)}</span><span class="lv-count">${countByLinhVuc(item.ten)}</span></li>`
        )
        .join("");
    }
    if (dashNhanh) {
      const list = data.thuTuc.filter((t) => t.nhanh).slice(0, 12);
      dashNhanh.innerHTML = list.length
        ? list
            .map(
              (t) =>
                `<li data-id="${t._id}"><span class="badge-nhanh">T4</span><span class="tt-name" title="${esc(t.ten)}">${esc(t.ten)}</span></li>`
            )
            .join("")
        : '<li class="empty">Chưa gắn cờ trong ngày</li>';
    }
  }

  function renderLinhVuc(list) {
    if (!grid) return;
    const visible = list.filter((lv) => countByLinhVuc(lv.ten) > 0);
    grid.innerHTML = visible
      .map((lv) => {
        const n = countByLinhVuc(lv.ten);
        const active = activeLinhVuc === lv.ten ? " is-active" : "";
        return `<article class="field-card${active}" data-name="${esc(lv.ten)}" title="${esc(lv.ten)}">
          <div class="icon"><img src="${LOGO}" alt="" /></div>
          <div class="name">${esc(lv.ten)}</div>
          <span class="count">${n} Thủ tục</span>
        </article>`;
      })
      .join("");
    if (linhVucCount) linhVucCount.textContent = visible.length + " lĩnh vực";
  }

  function renderThuTuc(list, resetPage = false) {
    lastList = list;
    if (resetPage) currentPage = 1;
    const totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
    currentPage = Math.min(Math.max(currentPage, 1), totalPages);
    const pageItems = list.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
    if (thuTucCount) thuTucCount.textContent = list.length + " thủ tục";

    if (pagination) pagination.hidden = list.length <= PAGE_SIZE;
    if (pageInfo) pageInfo.textContent = `Trang ${currentPage} / ${totalPages}`;
    if (btnPrevPage) btnPrevPage.disabled = currentPage <= 1;
    if (btnNextPage) btnNextPage.disabled = currentPage >= totalPages;

    if (activeLinhVuc) {
      if (thuTucTitle)
        thuTucTitle.textContent = "LĨNH VỰC " + activeLinhVuc.toUpperCase();
      if (btnBackLv) btnBackLv.hidden = false;
      if (ttFilterWrap) ttFilterWrap.hidden = false;
    } else {
      if (thuTucTitle) thuTucTitle.textContent = "📋 DANH SÁCH THỦ TỤC HÀNH CHÍNH";
      if (btnBackLv) btnBackLv.hidden = true;
      if (ttFilterWrap) ttFilterWrap.hidden = true;
      if (ttLocalSearch) ttLocalSearch.value = "";
    }

    if (!thuTucList) return;
    if (!list.length) {
      thuTucList.innerHTML =
        '<div class="tt-empty">Không có thủ tục phù hợp bộ lọc.</div>';
      return;
    }

    thuTucList.innerHTML = pageItems
      .map((tt, i) => {
        const ordinal = (currentPage - 1) * PAGE_SIZE + i + 1;
        return `<article class="tt-card" data-id="${tt._id}">
          <div class="tt-card-main">
            <span class="tt-stt">${ordinal}</span>
            <div class="tt-card-body">
              <div class="tt-tags">${tagsHtml(tt)}</div>
              <h3 class="tt-ten">${esc(tt.ten)}</h3>
            </div>
            <span class="tt-arrow">›</span>
          </div>
        </article>`;
      })
      .join("");
  }

  function openDetail(tt) {
    if (!detailOverlay || !detailBody || !tt) return;
    const steps = (tt.quyTrinh || [])
      .map((s, i) => `<li><span class="step-n">Bước ${i + 1}</span><span>${esc(s)}</span></li>`)
      .join("");
    const docs = (tt.thanhPhan || [])
      .map((d) => `<li>${esc(d)}</li>`)
      .join("");

    detailBody.innerHTML = `
      <div class="detail-tags">${tagsHtml(tt)}</div>
      <h3 class="detail-name" id="detailTitle">${esc(tt.ten)}</h3>

      <div class="detail-box info">
        <div class="box-label">📜 QUYẾT ĐỊNH BAN HÀNH</div>
        <p>${esc(tt.quyetDinh)}</p>
      </div>

      <div class="detail-meta">
        <div><strong>Cơ quan thực hiện</strong><span>${esc(tt.coQuan)}</span></div>
        <div><strong>Cấp giải quyết</strong><span>${esc(tt.cap)}</span></div>
        <div><strong>Thời hạn</strong><span>${esc(tt.thoiHan)}</span></div>
        <div><strong>Địa chỉ tiếp nhận</strong><span>Trung tâm PVHCC xã Vĩnh Bảo — Đường 20/8, xã Vĩnh Bảo, TP Hải Phòng</span></div>
        <div><strong>Hotline</strong><span>0823.919.686</span></div>
      </div>

      <div class="detail-box">
        <div class="box-label">🚩 QUY TRÌNH THỰC HIỆN & NỘP HỒ SƠ</div>
        <ol class="step-list">${steps}</ol>
        <a class="link-row" href="${esc(tt.dvcLink)}" target="_blank" rel="noopener">
          <span class="link-ico">📄</span>
          <span>
            <strong>${tt.formalityId ? "Xem chi tiết TTHC trên Cổng DVC Quốc gia" : "Tra cứu TTHC trên Cổng DVC Quốc gia"}</strong>
            <small>${tt.formalityId ? "formalityId: " + esc(tt.formalityId) : "Chưa có formalityId; mở kết quả tra cứu theo tên thủ tục"}</small>
          </span>
          <span class="link-go">Mở xem ↗</span>
        </a>
        <a class="link-row" href="${esc(tt.dvcTraCuu)}" target="_blank" rel="noopener" style="margin-top:0.5rem">
          <span class="link-ico">🔍</span>
          <span>
            <strong>Tìm “${esc(tt.ten)}” trên Cổng DVC</strong>
            <small>Tìm kiếm theo tên thủ tục (kết quả từ dichvucong.gov.vn)</small>
          </span>
          <span class="link-go">Tra cứu ↗</span>
        </a>
        <a class="link-row" href="${esc(tt.dvcTthcHome)}" target="_blank" rel="noopener" style="margin-top:0.5rem">
          <span class="link-ico">📋</span>
          <span>
            <strong>Danh mục TTHC Quốc gia</strong>
            <small>Trang chủ tra cứu thủ tục trên Cổng DVCQG</small>
          </span>
          <span class="link-go">Mở ↗</span>
        </a>
      </div>

      <div class="detail-box">
        <div class="box-label">📁 THÀNH PHẦN HỒ SƠ (tham khảo)</div>
        <ul class="doc-list">${docs}</ul>
        <p class="muted-note">Thành phần hồ sơ chính thức theo từng mã TTHC được công bố trên Cổng Dịch vụ công Quốc gia.</p>
      </div>

      <a class="btn-dvc" href="${esc(tt.dvcNop)}" target="_blank" rel="noopener">
        ${tt.formalityId ? "✨ NỘP HỒ SƠ / CHỌN ĐƠN VỊ TRÊN CỔNG DVC QUỐC GIA ↗" : "🔎 MỞ CỔNG DVC QUỐC GIA ĐỂ TRA CỨU, NỘP HỒ SƠ ↗"}
      </a>
      <p class="dvc-hint">
        ${tt.formalityId ? "Liên kết đã gắn formalityId và địa bàn Thành phố Hải Phòng → xã Vĩnh Bảo." : "Chưa có formalityId của thủ tục này; cần tra cứu, chọn đúng thủ tục và địa bàn Thành phố Hải Phòng → xã Vĩnh Bảo trước khi nộp."}<br/>
        Cổng DVC Quốc gia: <a href="${esc(tt.dvcNop)}" target="_blank" rel="noopener">dichvucong.gov.vn</a>
        · Cổng Hải Phòng: <a href="${esc(tt.dvcHp)}" target="_blank" rel="noopener">dichvucong.haiphong.gov.vn</a>
      </p>
    `;

    detailOverlay.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeDetail() {
    if (detailOverlay) detailOverlay.hidden = true;
    document.body.style.overflow = "";
  }

  function fillLinhVucSelect() {
    if (!filterLinhVuc) return;
    filterLinhVuc.innerHTML =
      '<option value="">Tất cả lĩnh vực</option>' +
      data.linhVuc
        .map(
          (lv) =>
            `<option value="${esc(lv.ten)}">${esc(lv.ten)} (${countByLinhVuc(lv.ten)})</option>`
        )
        .join("");
  }

  function applyFilters() {
    const keyword = normalizeText(searchInput?.value);
    const localQ = normalizeText(ttLocalSearch?.value);
    const lvSel = (filterLinhVuc?.value || activeLinhVuc || "").trim();
    const onlyNhanh = filterNhanh?.checked;
    const onlyMienPhi = filterMienPhi?.checked;
    const onlyPdg = filterPdg?.checked;

    let tt = data.thuTuc;
    if (lvSel) tt = tt.filter((t) => t.linhVuc === lvSel);
    if (onlyNhanh) tt = tt.filter((t) => t.nhanh);
    if (onlyMienPhi) tt = tt.filter((t) => isTrueFlag(t.mienPhiTrucTuyen));
    if (onlyPdg) tt = tt.filter((t) => isTrueFlag(t.phiDiaGioi));
    const q = localQ || keyword;
    if (q) {
      tt = tt.filter((t) =>
        [t.ten, t.ma, t.linhVuc, t.nganh].some((value) =>
          normalizeText(value).includes(q)
        )
      );
    }

    let lvList = data.linhVuc;
    if (keyword && !lvSel) {
      const namesInTt = new Set(tt.map((t) => t.linhVuc));
      lvList = data.linhVuc.filter(
        (lv) => normalizeText(lv.ten).includes(keyword) || namesInTt.has(lv.ten)
      );
    }

    renderLinhVuc(lvList);
    renderThuTuc(tt, true);
    updateFilterUi(tt.length);
  }

  function switchTab(tabId) {
    navBtns.forEach((b) => b.classList.toggle("active", b.dataset.tab === tabId));
    panels.forEach((p) => p.classList.toggle("active", p.id === tabId));
  }

  function openLinhVuc(name) {
    activeLinhVuc = name;
    if (filterLinhVuc) filterLinhVuc.value = name;
    applyFilters();
    switchTab("thu-tuc");
  }

  // Events
  navBtns.forEach((btn) => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));
  if (searchInput) searchInput.addEventListener("input", applyFilters);
  if (ttLocalSearch) ttLocalSearch.addEventListener("input", applyFilters);
  if (filterLinhVuc) {
    filterLinhVuc.addEventListener("change", () => {
      activeLinhVuc = filterLinhVuc.value || "";
      applyFilters();
      if (activeLinhVuc) switchTab("thu-tuc");
    });
  }
  if (filterNhanh) filterNhanh.addEventListener("change", applyFilters);
  if (filterMienPhi) filterMienPhi.addEventListener("change", applyFilters);
  if (filterPdg) filterPdg.addEventListener("change", applyFilters);
  if (btnClearSearch) {
    btnClearSearch.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      applyFilters();
      searchInput?.focus();
    });
  }
  if (btnPrevPage) {
    btnPrevPage.addEventListener("click", () => {
      if (currentPage <= 1) return;
      currentPage -= 1;
      renderThuTuc(lastList);
      document.getElementById("thu-tuc")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  if (btnNextPage) {
    btnNextPage.addEventListener("click", () => {
      const totalPages = Math.max(1, Math.ceil(lastList.length / PAGE_SIZE));
      if (currentPage >= totalPages) return;
      currentPage += 1;
      renderThuTuc(lastList);
      document.getElementById("thu-tuc")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  if (btnClearFilter) {
    btnClearFilter.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      if (ttLocalSearch) ttLocalSearch.value = "";
      if (filterLinhVuc) filterLinhVuc.value = "";
      if (filterNhanh) filterNhanh.checked = false;
      if (filterMienPhi) filterMienPhi.checked = false;
      if (filterPdg) filterPdg.checked = false;
      activeLinhVuc = "";
      applyFilters();
    });
  }
  if (btnBackLv) {
    btnBackLv.addEventListener("click", () => {
      activeLinhVuc = "";
      if (filterLinhVuc) filterLinhVuc.value = "";
      if (ttLocalSearch) ttLocalSearch.value = "";
      applyFilters();
      switchTab("linh-vuc");
    });
  }

  if (grid) {
    grid.addEventListener("click", (e) => {
      const card = e.target.closest(".field-card");
      if (!card) return;
      openLinhVuc(card.dataset.name);
    });
  }

  if (thuTucList) {
    thuTucList.addEventListener("click", (e) => {
      const card = e.target.closest(".tt-card");
      if (!card) return;
      openDetail(byId[card.dataset.id]);
    });
  }

  if (dashTopLv) {
    dashTopLv.addEventListener("click", (e) => {
      const li = e.target.closest("li[data-lv]");
      if (li) openLinhVuc(li.dataset.lv);
    });
  }
  if (dashNhanh) {
    dashNhanh.addEventListener("click", (e) => {
      const li = e.target.closest("li[data-id]");
      if (li) openDetail(byId[li.dataset.id]);
    });
  }

  document.querySelectorAll(".btn-dash[data-goto]").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.goto));
  });

  document.getElementById("btnCloseDetail")?.addEventListener("click", closeDetail);
  document.getElementById("btnXDetail")?.addEventListener("click", closeDetail);
  detailOverlay?.addEventListener("click", (e) => {
    if (e.target === detailOverlay) closeDetail();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetail();
  });

  function renderNganh() {
    const gridEl = document.getElementById("nganhGrid");
    const countEl = document.getElementById("nganhCount");
    if (!gridEl) return;
    const map = {};
    data.thuTuc.forEach((t) => {
      const n = t.nganh || "Khác";
      if (!map[n]) map[n] = [];
      map[n].push(t);
    });
    const names = Object.keys(map).sort((a, b) => a.localeCompare(b, "vi"));
    if (countEl) countEl.textContent = names.length + " ngành";
    gridEl.innerHTML = names
      .map(
        (n) =>
          `<article class="field-card nganh-card" data-nganh="${esc(n)}"><div class="icon"><img src="${LOGO}" alt="" /></div><div class="name">${esc(n)}</div><span class="count">${map[n].length} Thủ tục</span></article>`
      )
      .join("");
    gridEl.onclick = (e) => {
      const card = e.target.closest(".nganh-card");
      if (!card) return;
      const n = card.dataset.nganh;
      const list = data.thuTuc.filter((t) => (t.nganh || "Khác") === n);
      activeLinhVuc = "";
      if (filterLinhVuc) filterLinhVuc.value = "";
      renderThuTuc(list);
      if (thuTucTitle) thuTucTitle.textContent = "NGÀNH: " + n.toUpperCase();
      if (btnBackLv) {
        btnBackLv.hidden = false;
        btnBackLv.onclick = () => {
          switchTab("nganh");
          btnBackLv.hidden = true;
          applyFilters();
        };
      }
      switchTab("thu-tuc");
    };
  }

  function renderExtraTabs() {
    const extra = window.TTHC_EXTRA || {};
    const qdBox = document.getElementById("qdCongBoBox");
    if (qdBox && extra.quyetDinhCongBo) {
      qdBox.innerHTML = extra.quyetDinhCongBo
        .map(
          (q) =>
            `<article class="doc-card"><div class="doc-so">${esc(q.so)}</div><div class="doc-ngay">Ngày ${esc(q.ngay)}</div><h3>${esc(q.trichYeu)}</h3><span class="tag tag-lv">${esc(q.linhVuc)}</span>${q.link ? `<a class="doc-link" href="${esc(q.link)}" target="_blank" rel="noopener">Xem nguồn ↗</a>` : ""}</article>`
        )
        .join("");
    }
    const qdTheo = document.getElementById("qdTheoBox");
    if (qdTheo && extra.quyetDinhTheoTTHC) {
      qdTheo.innerHTML = extra.quyetDinhTheoTTHC
        .map(
          (g) =>
            `<div class="doc-block"><h3>${esc(g.nhom)}</h3><ul>${g.vanBan.map((v) => `<li>${esc(v)}</li>`).join("")}</ul></div>`
        )
        .join("");
    }
    const qtnb = document.getElementById("qtnbBox");
    if (qtnb && extra.quyTrinhNoiBo) {
      qtnb.innerHTML = extra.quyTrinhNoiBo
        .map(
          (b) =>
            `<div class="flow-step"><div class="flow-num">${b.buoc}</div><div><strong>${esc(b.ten)}</strong><p>${esc(b.moTa)}</p></div></div>`
        )
        .join("");
    }
    const phiBox = document.getElementById("phiBox");
    if (phiBox && extra.phiLePhi) {
      const p = extra.phiLePhi;
      let html = `<p class="doc-intro">${esc(p.ghiChuChung)}</p><h3 class="sub-h">Nghị quyết HĐND TP Hải Phòng</h3><div class="doc-list-cards">`;
      html += (p.nghiQuyetHP || [])
        .map(
          (q) =>
            `<article class="doc-card"><div class="doc-so">${esc(q.so)}</div><div class="doc-ngay">Ngày ${esc(q.ngay)}</div><h3>${esc(q.trichYeu)}</h3></article>`
        )
        .join("");
      html += `</div><h3 class="sub-h">Thông tư / quyết định Bộ ngành</h3><div class="doc-list-cards">`;
      html += (p.thongTuBo || [])
        .map(
          (q) =>
            `<article class="doc-card"><div class="doc-so">${esc(q.so)}</div><div class="doc-ngay">${esc(q.cq)} · ${esc(q.ngay)}</div><h3>${esc(q.trichYeu)}</h3></article>`
        )
        .join("");
      html += `</div>`;
      (p.mucThamKhao || []).forEach((nh) => {
        html += `<h3 class="sub-h">${esc(nh.nhom)}</h3><div class="table-wrap"><table class="data-table fee-table"><thead><tr><th>Nội dung</th><th>Mức thu (tham khảo)</th></tr></thead><tbody>`;
        html += nh.muc.map((m) => `<tr><td>${esc(m.ten)}</td><td><strong>${esc(m.muc)}</strong></td></tr>`).join("");
        html += `</tbody></table></div>`;
      });
      phiBox.innerHTML = html;
    }
  }

  if (footerSync) footerSync.textContent = dataSourceStatus;
  if (btnTop) {
    const syncTopButton = () => {
      btnTop.hidden = window.scrollY < 500;
    };
    window.addEventListener("scroll", syncTopButton, { passive: true });
    btnTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
    syncTopButton();
  }

  fillLinhVucSelect();
  renderDashboard();
  renderNganh();
  renderExtraTabs();
  applyFilters();
})();
