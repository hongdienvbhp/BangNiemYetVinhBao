#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract commune-relevant TTHC evidence from the official decision manifest.

Public Master Data is fed only by manifest entries classified as public_tthc.
Internal/process-only decisions are retained in the manifest/index but skipped.

For auto-discovered decisions, the extractor requires enough evidence to decide
whether the decision is effective at the evaluation date. If no explicit
effective-date clause can be found, the decision is marked for review instead
of being treated as current.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/source-audit/official-decision-manifest.json"
OUTPUT = ROOT / "data/source-audit/city-updates-current.json"

CODE_RE = re.compile(r"\b\d\.\d{6}\b")
TIME_OR_COLUMN_RE = re.compile(
    r"^(?:\d+(?:[.,]\d+)?\s*(?:ngày|giờ|tháng|năm)|"
    r"Không\b|Tại\b|-\s*Trung tâm|Trung tâm\b|Phí\b|Theo quy định|"
    r"Tối đa\b|Ngay trong\b)",
    re.IGNORECASE,
)

# Quyết định 3582 trình bày mã cũ và mã thay thế trong cùng một hàng bảng.
# Trích xuất văn bản thuần không giữ được ranh giới cột, nên khóa lại đúng quan
# hệ thay thế đã thể hiện trực tiếp trong phụ lục chính thức.
DECISION_ROW_OVERRIDES = {
    # Tên chép từ Phụ lục QĐ 186/QĐ-UBND (cột tên bị tách ký tự/dính cột).
    "186/QĐ-UBND": {
        "1.003851": {"name": "Cấp văn bản chấp thuận khai thác loài thủy sản nguy cấp, quý, hiếm (vì mục đích bảo tồn, nghiên cứu khoa học, nghiên cứu tạo nguồn giống ban đầu, hợp tác quốc tế)"},
        "1.003956": {"name": "Công nhận và giao quyền quản lý cho tổ chức cộng đồng"},
        "1.004498": {"name": "Sửa đổi, bổ sung nội dung quyết định công nhận và giao quyền quản lý cho tổ chức cộng đồng"},
        "1.004656": {"name": "Xác nhận nguồn gốc loài thủy sản thuộc Phụ lục Công ước quốc tế về buôn bán các loài động vật, thực vật hoang dã, nguy cấp; loài thủy sản nguy cấp, quý, hiếm có nguồn gốc khai thác từ tự nhiên"},
        "1.004680": {"name": "Xác nhận nguồn gốc loài thủy sản thuộc Phụ lục Công ước quốc tế về buôn bán các loài động vật, thực vật hoang dã nguy cấp; loài thủy sản nguy cấp, quý, hiếm có nguồn gốc từ nuôi trồng"},
    },
    # Tên chép từ Phụ lục QĐ 190/QĐ-UBND (cột thời hạn dính vào tên).
    "190/QĐ-UBND": {
        "1.003860": {"name": "Đăng ký chỉ định cơ sở kiểm nghiệm kiểm chứng về ATTP"},
        "2.001682": {"name": "Đăng ký chỉ định cơ sở kiểm nghiệm thực phẩm phục vụ quản lý nhà nước"},
    },
    # Phụ lục QĐ 2657/QĐ-UBND mục B: hai cột tên (được thay thế/thay thế) xen kẽ khi trích; dùng tên cùng mã trong bộ dữ liệu đã đối chiếu (js/data.js).
    "2657/QĐ-UBND": {
        "1.013225": {"name": "Cấp giấy phép xây dựng mới đối với công trình cấp III, cấp IV và nhà ở riêng lẻ"},
        "1.013227": {"name": "Gia hạn giấy phép xây dựng đối với công trình cấp III, cấp IV và nhà ở riêng lẻ"},
        "1.013228": {"name": "Cấp lại giấy phép xây dựng đối với công trình cấp III, cấp IV và nhà ở riêng lẻ"},
        "1.013229": {"name": "Cấp giấy phép xây dựng sửa chữa, cải tạo đối với công trình cấp III, cấp IV và nhà ở riêng lẻ"},
        "1.013232": {"name": "Cấp giấy phép di dời đối với công trình cấp III, cấp IV và nhà ở riêng lẻ"},
    },
    # Tên chép từ Phụ lục QĐ 3091/QĐ-UBND.
    "3091/QĐ-UBND": {
        "1.014034": {"name": "Đăng ký cập nhật, bổ sung thông tin trong hồ sơ đăng ký hộ kinh doanh, hiệu đính thông tin đăng ký hộ kinh doanh"},
    },
    # Tên chép từ Phụ lục QĐ 541/QĐ-UBND.
    "541/QĐ-UBND": {
        "1.014801": {"name": "Cấp, cấp lại Giấy xác nhận nuôi trồng thủy sản lồng bè, đối tượng thủy sản nuôi chủ lực (hoạt động trên nội địa thuộc phạm vi quản lý và cơ sở nuôi trồng thủy sản lồng bè thuộc thẩm quyền giao khu vực biển của Chủ tịch Ủy ban nhân dân cấp xã)"},
    },
    # Phụ lục QĐ 2295/QĐ-UBND, mục I 'TTHC được thay thế': mã ở cột STT là TTHC được thay thế (bãi bỏ), mã trong '(Mã số TTHC: …)' là TTHC thay thế.
    "2295/QĐ-UBND": {
        "1.012958": {"sectionStatus": "repealed"},
        "1.012959": {"sectionStatus": "repealed"},
        "3.000301": {"sectionStatus": "repealed"},
        "1.005008": {"sectionStatus": "repealed"},
        "3.000297": {"sectionStatus": "repealed"},
        "3.000302": {"sectionStatus": "repealed"},
        "3.000306": {"sectionStatus": "repealed"},
        "1.004999": {"sectionStatus": "repealed"},
        "3.000299": {"sectionStatus": "repealed"},
        "3.000304": {"sectionStatus": "repealed"},
        "1.004991": {"sectionStatus": "repealed"},
        "3.000300": {"sectionStatus": "repealed"},
        "3.000305": {"sectionStatus": "repealed"},
        "3.000309": {"sectionStatus": "repealed"},
        "1.012944": {"name": "Thành lập hoặc cho phép thành lập trường trung học phổ thông, trường phổ thông có nhiều cấp học có cấp học cao nhất là trung học phổ thông"},
        "1.012954": {"name": "Cho phép trường trung học phổ thông, trường phổ thông có nhiều cấp học có cấp học cao nhất là trung học phổ thông hoạt động giáo dục"},
        "1.012955": {"name": "Sáp nhập, chia, tách trường trung học phổ thông, trường phổ thông có nhiều cấp học có cấp học cao nhất là trung học phổ thông"},
        "1.012956": {"name": "Giải thể trường trung học phổ thông, trường phổ thông có nhiều cấp học có cấp học cao nhất là trung học phổ thông (theo đề nghị của tổ chức, cá nhân thành lập trường)"},
    },
    # Tên chép từ Phụ lục QĐ 777/QĐ-UBND và QĐ 394/QĐ-UBND (cột tên bị xuống trang/dính cột).
    "777/QĐ-UBND": {
        "1.005021": {"name": "Phê duyệt quy trình vận hành, khai thác bến phà, bến khách ngang sông sử dụng phà một lưỡi chở hành khách và xe ô tô"},
    },
    "394/QĐ-UBND": {
        # Phụ lục QĐ 394/QĐ-UBND, mục A2 'TTHC thay thế': 1.011516 được thay bằng 2.002835; 1.009669 được thay bằng 1.014716.
        "1.011516": {"sectionStatus": "repealed"},
        "1.009669": {"sectionStatus": "repealed"},
        "2.002835": {"name": "Đăng ký khai thác nước mặt, nước biển, đăng ký sử dụng mặt nước, đào hồ, ao, sông, suối, kênh, mương, rạch"},
    },
    # Phụ lục QĐ 3249/QĐ-UBND: 04 TTHC cấp xã lĩnh vực giảm nghèo "bị bãi bỏ từ ngày 01/01/2027".
    "3249/QĐ-UBND": {
        "1.011606": {"rowEffectiveDate": "2027-01-01"},
        "1.011607": {"rowEffectiveDate": "2027-01-01"},
        "1.011608": {"rowEffectiveDate": "2027-01-01"},
        "3.000412": {"rowEffectiveDate": "2027-01-01"},
    },
    # Tên chép từ Phụ lục QĐ 1635/QĐ-UBND (cột tên dính cột thời hạn/bị xuống trang).
    "1635/QĐ-UBND": {
        "1.002407": {
            "name": "Xét, cấp học bổng chính sách",
            "levelHint": "shared_including_commune",
        },
        "1.008722": {
            "name": "Chuyển đổi nhà trẻ, trường mẫu giáo, trường mầm non tư thục do nhà đầu tư nước ngoài đầu tư sang nhà trẻ, trường mẫu giáo, trường mầm non tư thục hoạt động không vì lợi nhuận",
        },
        "1.008723": {
            "name": "Chuyển đổi trường trung học phổ thông tư thục, trường phổ thông tư thục có nhiều cấp học có cấp học cao nhất là trung học phổ thông do nhà đầu tư trong nước đầu tư và bảo đảm điều kiện hoạt động; cơ sở giáo dục phổ thông tư thục do nhà đầu tư nước ngoài đầu tư sang trường trung học phổ thông tư thục, trường phổ thông tư thục có nhiều cấp học có cấp học cao nhất là trung học phổ thông hoạt động không vì lợi nhuận",
        },
        "1.008724": {
            "name": "Chuyển đổi nhà trẻ, trường mẫu giáo, trường mầm non tư thục do nhà đầu tư trong nước đầu tư sang nhà trẻ, trường mẫu giáo, trường mầm non tư thục hoạt động không vì lợi nhuận",
        },
    },
    # Tên chép từ Phụ lục QĐ 1747/QĐ-UBND.
    "1747/QĐ-UBND": {
        "1.008720": {
            "name": "Chuyển đổi cơ sở giáo dục mầm non tư thục do cơ quan đại diện ngoại giao nước ngoài, tổ chức quốc tế liên chính phủ đề nghị sang cơ sở giáo dục mầm non tư thục hoạt động không vì lợi nhuận",
        },
        "1.012969": {
            "name": "Thành lập hoặc cho phép thành lập trung tâm học tập cộng đồng",
        },
        "1.013751": {
            "name": "Cho phép thành lập trung tâm giáo dục thường xuyên, trung tâm giáo dục nghề nghiệp - giáo dục thường xuyên tư thục",
        },
        "1.013759": {
            "name": "Cho phép thành lập cơ sở giáo dục nghề nghiệp, cơ sở giáo dục nghề nghiệp cho người khuyết tật, phân hiệu của trường trung cấp tư thục",
        },
    },
    # Tên chép từ Phụ lục I QĐ 1847/QĐ-UBND.
    "1847/QĐ-UBND": {
        "2.002854": {
            "name": "Chuyển trường và tiếp nhận học sinh",
        },
        "2.002855": {
            "name": "Tiếp nhận học sinh Việt Nam từ nước ngoài về nước",
        },
        "2.002856": {
            "name": "Tiếp nhận học sinh người nước ngoài",
        },
        "2.002857": {
            "name": "Tiếp nhận học sinh xin học lại",
        },
    },
    # Tên chép từ Phụ lục I QĐ 1897/QĐ-UBND.
    "1897/QĐ-UBND": {
        "1.002571": {
            "name": "Đăng ký, cấp giấy chứng nhận kiểm dịch động vật trên cạn tham gia hội chợ, triển lãm, thi đấu thể thao, biểu diễn nghệ thuật; sản phẩm động vật trên cạn tham gia hội chợ, triển lãm",
        },
        "1.010091": {
            "name": "Hỗ trợ khám chữa bệnh, trợ cấp tai nạn cho lực lượng xung kích phòng chống thiên tai cấp xã trong trường hợp chưa tham gia bảo hiểm y tế, bảo hiểm xã hội",
        },
        "1.010092": {
            "name": "Trợ cấp tiền tuất, tai nạn (đối với trường hợp tai nạn suy giảm khả năng lao động từ 5% trở lên) cho lực lượng xung kích phòng chống thiên tai cấp xã chưa tham gia bảo hiểm xã hội",
        },
        "1.010733": {
            "name": "Thẩm định báo cáo đánh giá tác động môi trường",
        },
        "1.013644": {
            "name": "Cấp phép đối với các hoạt động liên quan đến đê điều thuộc trách nhiệm của Uỷ ban nhân dân tỉnh",
        },
        "1.014132": {
            "name": "Hủy đăng ký dự án",
        },
        "1.014133": {
            "name": "Cấp tín chỉ các-bon theo cơ chế trao đổi, bù trừ tín chỉ các-bon trong nước",
        },
        "1.014136": {
            "name": "Đăng ký/Điều chỉnh dự án theo cơ chế trao đổi, bù trừ tín chỉ các-bon trong nước",
        },
        "2.001558": {
            "name": "Cấp giấy chứng nhận kiểm dịch động vật, sản phẩm động vật thủy sản xuất khẩu mang theo người, gửi qua đường bưu điện",
        },
        "2.002849": {
            "name": "Chuyển quyền sở hữu hạn ngạch phát thải khí nhà kính, tín chỉ các-bon ngoài hệ thống giao dịch các-bon",
        },
    },
    # Tên chép từ Phụ lục QĐ 3856/QĐ-UBND.
    "3856/QĐ-UBND": {
        "1.000658": {
            "name": "Thủ tục cấp Giấy chứng nhận KP đối với kim cương thô xuất khẩu theo Quy chế Chứng nhận KP",
        },
    },
    # Tên chép từ Phụ lục QĐ 3904/QĐ-UBND.
    "3904/QĐ-UBND": {
        "2.000890": {
            "name": "Cấp phép thành lập văn phòng giám định tư pháp",
        },
    },
    # Tên chép từ Phụ lục QĐ 3957/QĐ-UBND.
    "3957/QĐ-UBND": {
        "1.116556": {
            "name": "Thủ tục cung cấp thông tin theo yêu cầu (dành cho cá nhân)",
        },
        "1.116557": {
            "name": "Thủ tục cung cấp thông tin theo yêu cầu (dành cho công dân thông qua tổ chức, đoàn thể, doanh nghiệp)",
        },
    },
    # Tên chép từ Phụ lục QĐ 4016/QĐ-UBND.
    "4016/QĐ-UBND": {
        "1.003593": {
            "name": "Cấp giấy xác nhận nguyên liệu thủy sản khai thác (theo yêu cầu)",
        },
    },
    # Tên/lĩnh vực chép từ Phụ lục QĐ 467/QĐ-UBND (lớp chữ PDF bị tách ký tự, dính cột thời hạn).
    "467/QĐ-UBND": {
        # Mục C "Thủ tục hành chính dùng chung" (sau mục A cấp tỉnh, B cấp xã).
        "2.000635": {
            "levelHint": "shared_including_commune",
        },
        "2.002516": {
            "levelHint": "shared_including_commune",
        },
        "1.000893": {
            "name": "Đăng ký khai sinh có yếu tố nước ngoài cho người đã có hồ sơ, giấy tờ cá nhân",
        },
        "1.001695": {
            "name": "Đăng ký khai sinh kết hợp đăng ký nhận cha, mẹ, con có yếu tố nước ngoài",
        },
        "2.000547": {
            "name": "Ghi vào sổ hộ tịch việc hộ tịch khác của công dân Việt Nam đã được giải quyết tại cơ quan có thẩm quyền của nước ngoài (khai sinh; giám hộ; nhận cha, mẹ, con; xác định cha, mẹ, con; nuôi con nuôi; khai tử; thay đổi hộ tịch)",
        },
        "2.000554": {
            "name": "Ghi vào sổ hộ tịch việc ly hôn, hủy việc kết hôn của công dân Việt Nam đã được giải quyết tại cơ quan có thẩm quyền của nước ngoài",
        },
        "2.000748": {
            "name": "Thay đổi, cải chính, bổ sung thông tin hộ tịch, xác định lại dân tộc có yếu tố nước ngoài",
        },
        "2.000756": {
            "name": "Đăng ký chấm dứt giám hộ có yếu tố nước ngoài",
        },
        "2.000779": {
            "name": "Đăng ký nhận cha, mẹ, con có yếu tố nước ngoài",
        },
        "2.000908": {
            "name": "Cấp bản sao từ sổ gốc",
            "field": "CHỨNG THỰC",
            "levelHint": "shared_including_commune",
        },
        "1.013818": {
            "field": "CÔNG CHỨNG",
        },
        "1.013836": {
            "field": "CÔNG CHỨNG",
        },
        "1.001842": {
            "field": "QUẢN TÀI VIÊN",
        },
        "1.002626": {
            "field": "QUẢN TÀI VIÊN",
        },
        "1.002681": {
            "field": "QUẢN TÀI VIÊN",
        },
        "2.001117": {
            "field": "QUẢN TÀI VIÊN",
        },
        "2.001130": {
            "name": "Cấp chứng chỉ hành nghề Quản tài viên đối với luật sư, kiểm toán viên, người có trình độ cử nhân luật, kinh tế, kế toán, tài chính, ngân hàng và có thời gian công tác trong lĩnh vực được đào tạo từ 05 năm trở lên",
            "field": "QUẢN TÀI VIÊN",
        },
    },
    # Tên chép từ Phụ lục QĐ 556/QĐ-UBND (cột tên bị dính cột trình tự/thời hạn).
    "556/QĐ-UBND": {
        "1.003005": {
            "name": "Giải quyết việc người nước ngoài cư trú ở khu vực biên giới nước láng giềng nhận trẻ em Việt Nam làm con nuôi",
        },
        "1.003198": {
            "name": "Cấp giấy xác nhận công dân Việt Nam ở trong nước đủ điều kiện nhận trẻ em nước ngoài làm con nuôi",
        },
        "1.003976": {
            "name": "Giải quyết việc nuôi con nuôi có yếu tố nước ngoài đối với trẻ em sống ở cơ sở nuôi dưỡng",
        },
        "2.002363": {
            "name": "Ghi vào Sổ đăng ký nuôi con nuôi việc nuôi con nuôi đã được giải quyết tại cơ quan có thẩm quyền của nước ngoài",
        },
    },
    # Tên/lĩnh vực chép từ Phụ lục QĐ 1349/QĐ-UBND (tiêu đề lĩnh vực trong bảng).
    "1349/QĐ-UBND": {
        "1.001323": {
            "name": "Cấp sửa đổi, bổ sung Giấy phép phân phối sản phẩm thuốc lá",
        },
        "1.013987": {
            "name": "Chấp thuận các tài liệu quản lý an toàn đối với công trình dầu khí thuộc thẩm quyền giải quyết của Ủy ban nhân dân cấp tỉnh",
            "field": "DẦU KHÍ",
        },
        "1.014967": {
            "name": "Cấp Giấy phép vận chuyển hàng hóa nguy hiểm loại 1 (trừ vật liệu nổ công nghiệp, tiền chất thuốc nổ), 2, 3, 4, 9",
            "field": "VẬN CHUYỂN HÀNG HÓA NGUY HIỂM",
        },
        "1.014968": {
            "name": "Cấp điều chỉnh Giấy phép vận chuyển hàng hóa nguy hiểm loại 1 (trừ vật liệu nổ công nghiệp, tiền chất thuốc nổ), 2, 3, 4, 9",
            "field": "VẬN CHUYỂN HÀNG HÓA NGUY HIỂM",
        },
        "1.014969": {
            "name": "Cấp lại Giấy phép vận chuyển hàng hóa nguy hiểm loại 1 (trừ vật liệu nổ công nghiệp, tiền chất thuốc nổ), 2, 3, 4, 9",
            "field": "VẬN CHUYỂN HÀNG HÓA NGUY HIỂM",
        },
        "2.000162": {
            "name": "Cấp sửa đổi, bổ sung Giấy phép bán lẻ sản phẩm thuốc lá",
        },
        "2.000181": {
            "name": "Cấp Giấy phép bán lẻ sản phẩm thuốc lá",
        },
    },
    # Tên/lĩnh vực chép từ Phụ lục QĐ 1353/QĐ-UBND (cột tên bị dính cột thời hạn).
    "1353/QĐ-UBND": {
        # Mã có mặt ở cả mục A (cấp tỉnh) và mục B (cấp xã) của Phụ lục.
        "2.000884": {
            "levelHint": "shared_including_commune",
        },
        "2.001008": {
            "levelHint": "shared_including_commune",
        },
        "2.000908": {
            "name": "Cấp bản sao từ sổ gốc",
        },
        "2.000927": {
            "name": "Sửa lỗi sai sót trong giao dịch",
        },
        "2.001019": {
            "name": "Chứng thực di chúc",
        },
        "1.013803": {
            "field": "CÔNG CHỨNG",
        },
    },
    # Lĩnh vực theo tiêu đề mục A1 Phụ lục QĐ 2127/QĐ-UBND.
    "2127/QĐ-UBND": {
        "2.000578": {
            "field": "VẬT LIỆU NỔ CÔNG NGHIỆP, TIỀN CHẤT THUỐC NỔ",
        },
    },
    # Tên/lĩnh vực chép từ Phụ lục QĐ 2380/QĐ-UBND.
    "2380/QĐ-UBND": {
        "1.000414": {
            "name": "Rút tiền ký quỹ của doanh nghiệp cho thuê lại lao động",
            "field": "LAO ĐỘNG - TIỀN LƯƠNG",
        },
        "1.015021": {
            "field": "QUẢN LÝ LAO ĐỘNG NGOÀI NƯỚC",
        },
    },
    "3879/QĐ-UBND": {
        # Tên chép từ Phụ lục QĐ 3879/QĐ-UBND (lớp chữ PDF bị tách ký tự).
        "1.004889": {
            "name": "Công nhận bằng tốt nghiệp trung học cơ sở, bằng tốt nghiệp trung học phổ thông, giấy chứng nhận hoàn thành chương trình giáo dục phổ thông do cơ sở giáo dục nước ngoài cấp để sử dụng tại Việt Nam",
        },
    },
    "3582/QĐ-UBND": {
        "2.001023": {
            "name": "Liên thông các thủ tục hành chính về đăng ký khai sinh, cấp Thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi",
            "sectionStatus": "repealed",
        },
        "2.002621": {
            "name": "Đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi",
            "sectionStatus": "repealed",
        },
        "2.000986": {
            "name": "Liên thông thủ tục hành chính về đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế cho trẻ em dưới 6 tuổi",
            "sectionStatus": "repealed",
        },
        "2.002622": {
            "name": "Đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất",
            "sectionStatus": "repealed",
        },
        "3.000722": {
            "name": "Liên thông điện tử: đăng ký khai sinh, đăng ký thường trú, cấp thẻ bảo hiểm y tế, cấp thẻ căn cước cho trẻ em dưới 6 tuổi",
            "sectionStatus": "new",
            # Cột "Địa điểm thực hiện" của Phụ lục: Trung tâm PVHCC thành phố và cấp xã.
            "levelHint": "shared_including_commune",
            "communeReceptionEvidence": True,
        },
        "2.002913": {
            "name": "Liên thông điện tử: đăng ký khai tử, xóa đăng ký thường trú, giải quyết mai táng phí, tử tuất",
            "sectionStatus": "new",
            # Cột "Địa điểm thực hiện" của Phụ lục: Trung tâm PVHCC thành phố và cấp xã.
            "levelHint": "shared_including_commune",
            "communeReceptionEvidence": True,
        },
    },
    # Ba tên trong QĐ 3584 tiếp tục ở đầu trang kế tiếp của phụ lục.
    "3584/QĐ-UBND": {
        "1.004191": {
            "name": "Thủ tục sửa đổi, bổ sung/cấp lại Giấy phép: kinh doanh tạm nhập, tái xuất; tạm nhập, tái xuất theo hình thức khác; tạm xuất, tái nhập; kinh doanh chuyển khẩu",
        },
        "1.000477": {
            "name": "Thủ tục cấp Giấy phép quá cảnh hàng hóa cấm xuất khẩu, cấm nhập khẩu; hàng hóa tạm ngừng xuất khẩu, tạm ngừng nhập khẩu; hàng hóa cấm kinh doanh theo quy định pháp luật",
        },
        "1.013771": {
            "name": "Thủ tục cấp Giấy phép gia công hàng hóa thuộc diện hàng hóa cấm xuất khẩu, cấm nhập khẩu; hàng hóa tạm ngừng xuất khẩu, tạm ngừng nhập khẩu",
        },
    },
    # QĐ 3626 tách riêng Phụ lục B cấp xã và Phụ lục C dùng chung.
    # Khóa theo chính phụ lục ký số để dữ liệu công dân chỉ nhận đúng cấp xã.
    "3643/QĐ-UBND": {
        "2.000552": {
            "name": "Cấp lại Giấy phép hoạt động đối với trạm, điểm sơ cấp cứu chữ thập đỏ khi thay đổi địa điểm",
        },
        "1.006780": {
            "name": "Cấp lại Giấy phép hoạt động đối với trạm, điểm sơ cấp cứu chữ thập đỏ do mất, rách, hỏng hoặc sai sót thông tin",
        },
    },
    "3626/QĐ-UBND": {
        "2.001909": {
            "name": "Thủ tục tiếp công dân tại cấp xã",
            "field": "TIẾP CÔNG DÂN",
            "levelHint": "commune",
            "communeReceptionEvidence": True,
        },
        "2.001801": {
            "name": "Thủ tục xử lý đơn tại cấp xã",
            "field": "XỬ LÝ ĐƠN",
            "levelHint": "commune",
            "communeReceptionEvidence": True,
        },
        "2.002409": {
            "name": "Thủ tục giải quyết khiếu nại lần đầu tại xã",
            "field": "KHIẾU NẠI",
            "levelHint": "commune",
            "communeReceptionEvidence": True,
        },
        "2.002396": {
            "name": "Giải quyết tố cáo cấp xã",
            "field": "TỐ CÁO",
            "levelHint": "commune",
            "communeReceptionEvidence": True,
        },
        "2.002401": {
            "levelHint": "shared",
            "communeReceptionEvidence": False,
        },
        "2.002403": {
            "levelHint": "shared",
            "communeReceptionEvidence": False,
        },
    },
}


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").lower()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def section_status(line: str, current: str) -> str:
    value = fold(line)
    if "danh muc" not in value and not re.match(r"^[a-d][.)]\s", value):
        return current
    if "bi bai bo" in value:
        return "repealed"
    if "thay the" in value:
        return "replaced_or_replacement"
    if "sua doi" in value or "bo sung" in value:
        return "modified"
    if "ban hanh moi" in value:
        return "new"
    return current


def level_hint(line: str, current: str) -> str:
    value = fold(line).strip(" .:;-|")
    # Chỉ tiêu đề/phân mục pháp lý mới được đổi cấp giải quyết. Cụm "cấp xã"
    # trong cột nơi tiếp nhận không phải bằng chứng TTHC thuộc thẩm quyền cấp xã.
    standalone_level = bool(
        re.fullmatch(r"[a-d][.)]\s*(?:cap xa|cap tinh|dung chung(?:.*cap xa)?)", value)
    )
    if "thu tuc hanh chinh" not in value and not standalone_level:
        return current
    if "dung chung" in value:
        return "shared_including_commune" if "cap xa" in value else "shared"
    if "cap xa" in value:
        return "commune"
    if "cap tinh" in value:
        return "province"
    return current


def extract_name(lines: list[str], line_index: int, code: str) -> str:
    line = lines[line_index]
    after = line.split(code, 1)[1].strip(" .:-") if code in line else ""
    parts = [after] if after else []
    for j in range(line_index + 1, min(len(lines), line_index + 16)):
        value = re.sub(r"\s+", " ", lines[j]).strip()
        if not value:
            continue
        if CODE_RE.search(value):
            break
        if TIME_OR_COLUMN_RE.match(value) and parts:
            break
        if value == "STT" or "Mã TTHC" in value or "Tên TTHC" in value:
            continue
        parts.append(value)
        if len(" ".join(parts)) > 220:
            break
    return re.sub(r"\s+", " ", " ".join(parts)).strip(" .;:-|")


def context_is_commune(lines: list[str], idx: int, level: str) -> bool:
    if level in {"commune", "shared_including_commune"}:
        return True
    context = " ".join(lines[max(0, idx - 20) : min(len(lines), idx + 80)])
    value = fold(context)
    compact = re.sub(r"[^a-z0-9]", "", value)
    return (
        ("trung tam" in value and ("cap xa" in value or "cac xa" in value or "pvhcc cac xa" in value))
        or "trung tam phuc vu hcc cac xa" in value
        or "trung tam phuc vu hanh chinh cong xa" in value
        or "trungtamphucvuhanhchinhcongcapxa" in compact
        or "trungtamphucvuhanhchinhcongxa" in compact
        or "trungtamphucvuhcccacxa" in compact
    )


def row_is_commune(lines: list[str], idx: int, level: str) -> bool:
    if level in {"commune", "shared_including_commune"}:
        return True
    row: list[str] = [lines[idx]]
    for j in range(idx + 1, min(len(lines), idx + 25)):
        if CODE_RE.search(lines[j]):
            break
        row.append(lines[j])
    value = re.sub(r"\s+", " ", fold(" ".join(row)))
    compact = re.sub(r"[^a-z0-9]", "", value)
    return bool(
        re.search(r"trung tam.{0,80}(cap xa|cac xa|xa, phuong|pvhcc xa)", value)
        or "trungtamphucvuhanhchinhcongcapxa" in compact
        or "trungtamphucvuhanhchinhcongxa" in compact
        or "trungtamphucvuhanhchinhcongcacxa" in compact
    )


def parse_iso_date(day: str, month: str, year: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def detect_effective_date(reader: PdfReader, decision_date: str) -> tuple[str | None, str]:
    sample = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
    value = fold(sample)
    numeric_patterns = [
        r"co hieu luc(?: thi hanh)? ke tu ngay\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"co hieu luc(?: thi hanh)? tu ngay\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"co hieu luc(?: thi hanh)? tu\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"co hieu luc(?: thi hanh)? ke tu\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        r"co hieu luc(?: thi hanh)? ke tu ngay\s*(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})",
        r"co hieu luc(?: thi hanh)? tu ngay\s*(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})",
    ]
    for pattern in numeric_patterns:
        match = re.search(pattern, value, re.I)
        if match:
            return parse_iso_date(match.group(1), match.group(2), match.group(3)), "explicit_date_clause"

    if re.search(r"co hieu luc(?: thi hanh)?(?: ke)? tu ngay ky", value, re.I):
        return decision_date or None, "effective_from_signing_clause"

    return None, "effective_clause_not_found"


def repair_split_tthc_codes(lines: list[str]) -> list[str]:
    """Join canonical 1.xxxxxx codes split by PDF text extraction after 5 decimals."""
    out = list(lines)
    for i in range(len(out) - 1):
        partial = re.search(r"\b(\d\.\d{5})$", out[i])
        if partial and re.fullmatch(r"\d", out[i + 1].strip()):
            out[i] = out[i] + out[i + 1].strip()
            out[i + 1] = ""
    return out


def merge_rows(rows: list[dict]) -> dict[str, dict]:
    priority = {
        "repealed": 5,
        "replaced_or_replacement": 4,
        "modified": 3,
        "new": 2,
        "published": 1,
    }
    merged: dict[str, dict] = {}
    for row in rows:
        code = row["code"]
        previous = merged.get(code)
        if not previous:
            merged[code] = row
            continue
        if priority.get(row["sectionStatus"], 0) > priority.get(previous["sectionStatus"], 0):
            previous["sectionStatus"] = row["sectionStatus"]
        previous["communeReceptionEvidence"] = bool(
            previous["communeReceptionEvidence"] or row["communeReceptionEvidence"]
        )
        if len(row.get("name") or "") > len(previous.get("name") or "") and len(row.get("name") or "") <= 240:
            previous["name"] = row["name"]
        previous["context"] = (previous.get("context", "") + " | " + row.get("context", ""))[:2400]
    return merged


def extract_decision(meta: dict, as_of: str) -> dict:
    file_path = str(meta.get("filePath") or "")
    if not file_path:
        raise ValueError(f"{meta.get('decisionNo')}: missing filePath")
    path = ROOT / file_path
    if not path.is_file():
        raise FileNotFoundError(f"{meta.get('decisionNo')}: missing PDF {file_path}")

    reader = PdfReader(str(path))
    decision_date = str(meta.get("decisionDate") or "")
    effective_date = meta.get("effectiveDate")
    effective_source = "manifest"
    if not effective_date:
        detected, source = detect_effective_date(reader, decision_date)
        effective_date = detected
        effective_source = source
    if not effective_date and decision_date:
        # Quy tắc nghiệp vụ (chỉ đạo 29/9/2026): quyết định không ghi điều khoản
        # hiệu lực thì có hiệu lực kể từ ngày ký.
        effective_date = decision_date
        effective_source = "default_effective_from_signing_date"

    ingest_status = str(meta.get("ingestStatus") or "")
    if ingest_status == "reviewed_no_commune_change":
        current_state = "reviewed_no_commune_change"
        effective_source = "manual_scope_review"
    elif ingest_status == "reviewed_pending_effective_date":
        current_state = "reviewed_pending_effective_date"
        effective_source = "manual_effective_date_review"
    elif effective_date:
        current_state = "future_effective" if effective_date > as_of else "current_or_immediate_unless_repealed"
    elif ingest_status == "applied":
        # Decisions marked applied have independent manual implementation evidence.
        current_state = "current_or_immediate_unless_repealed"
        effective_source = "baseline_manual_verification"
    else:
        current_state = "needs_effective_date_review"

    if not meta.get("field") and ingest_status != "applied":
        current_state = "needs_field_review"

    # receptionEvidenceScope = "row": chỉ chấp nhận bằng chứng tiếp nhận cấp xã nằm
    # trong chính dòng của mã (không dùng cửa sổ rộng -20/+80 dòng).
    row_scope = meta.get("receptionEvidenceScope") == "row"
    rows: list[dict] = []
    status = "published"
    level = ""
    start_page = 2 if len(reader.pages) > 2 else 0
    for page_index, page in enumerate(reader.pages):
        if page_index < start_page:
            continue
        text = page.extract_text() or ""
        lines = repair_split_tthc_codes([re.sub(r"\s+", " ", item).strip() for item in text.splitlines()])
        for i, line in enumerate(lines):
            if not line:
                continue
            status = section_status(line, status)
            level = level_hint(line, level)
            for match in CODE_RE.finditer(line):
                code = match.group(0)
                rows.append(
                    {
                        "code": code,
                        "name": extract_name(lines, i, code),
                        "sectionStatus": status,
                        "levelHint": level,
                        "communeReceptionEvidence": (
                            row_is_commune(lines, i, level)
                            if row_scope
                            else context_is_commune(lines, i, level)
                        ),
                        "page": page_index + 1,
                        "context": " ".join(lines[max(0, i - 3) : min(len(lines), i + 18)])[:1800],
                    }
                )

    merged = merge_rows(rows)
    for code, override in DECISION_ROW_OVERRIDES.get(str(meta.get("decisionNo") or ""), {}).items():
        if code in merged:
            merged[code].update(override)
    return {
        "decisionNo": meta.get("decisionNo"),
        "decisionDate": decision_date,
        "publishedDate": meta.get("publishedDate") or "",
        "effectiveDate": effective_date,
        "effectiveDateSource": effective_source,
        "currentStateAtAsOf": current_state,
        "classification": meta.get("classification"),
        "ingestStatus": ingest_status,
        "field": meta.get("field") or "",
        "title": meta.get("title") or "",
        "articleUrl": meta.get("articleUrl"),
        "pdfUrl": meta.get("pdfUrl"),
        "filePath": file_path,
        "pdfSha256": sha256(path),
        "pageCount": len(reader.pages),
        "rows": sorted(merged.values(), key=lambda item: item["code"]),
    }


def semantic_payload(payload: dict) -> dict:
    clone = json.loads(json.dumps(payload, ensure_ascii=False))
    clone.pop("asOf", None)
    return clone


def write_if_semantically_changed(payload: dict) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if OUTPUT.exists():
        old = load_json(OUTPUT)
        if semantic_payload(old) == semantic_payload(payload):
            return False
    OUTPUT.write_text(rendered, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()

    manifest = load_json(MANIFEST)
    public_meta = [
        item
        for item in manifest.get("decisions", [])
        if item.get("classification") == "public_tthc" and item.get("filePath")
    ]
    decisions = [extract_decision(meta, args.as_of) for meta in public_meta]

    all_rows: list[dict] = []
    for decision in decisions:
        for row in decision["rows"]:
            all_rows.append(
                {
                    "decisionNo": decision["decisionNo"],
                    "decisionDate": decision["decisionDate"],
                    "publishedDate": decision["publishedDate"],
                    "effectiveDate": decision["effectiveDate"],
                    "effectiveDateSource": decision["effectiveDateSource"],
                    "currentStateAtAsOf": decision["currentStateAtAsOf"],
                    "classification": decision["classification"],
                    "ingestStatus": decision["ingestStatus"],
                    "field": decision["field"],
                    "articleUrl": decision["articleUrl"],
                    "pdfUrl": decision["pdfUrl"],
                    "pdfSha256": decision["pdfSha256"],
                    **row,
                }
            )
            # Mục có ngày hiệu lực riêng (ghi trong DECISION_ROW_OVERRIDES): tính lại
            # trạng thái theo ngày đánh giá, chỉ khi quyết định đã có hiệu lực chung.
            item = all_rows[-1]
            if row.get("rowEffectiveDate") and decision["currentStateAtAsOf"] in {
                "current_or_immediate_unless_repealed",
                "future_effective",
            }:
                item["effectiveDate"] = row["rowEffectiveDate"]
                item["effectiveDateSource"] = "row_effective_date_override"
                item["currentStateAtAsOf"] = (
                    "future_effective" if row["rowEffectiveDate"] > args.as_of else "current_or_immediate_unless_repealed"
                )

    payload = {
        "format": "haiphong-city-tthc-updates",
        "version": 2,
        "asOf": args.as_of,
        "scope": (
            "Public TTHC decisions in the official decision manifest. "
            "Internal/process-only decisions are retained in the manifest/source index but excluded here."
        ),
        "decisions": decisions,
        "rows": all_rows,
        "summary": {
            "decisions": len(decisions),
            "uniqueCodes": len({item["code"] for item in all_rows}),
            "communeReceptionCodes": len(
                {item["code"] for item in all_rows if item["communeReceptionEvidence"]}
            ),
            "repealedCodes": len(
                {item["code"] for item in all_rows if item["sectionStatus"] == "repealed"}
            ),
            "futureEffectiveCodes": len(
                {item["code"] for item in all_rows if item["currentStateAtAsOf"] == "future_effective"}
            ),
            "needsReviewDecisions": sum(
                1 for item in decisions if str(item["currentStateAtAsOf"]).startswith("needs_")
            ),
        },
    }
    changed = write_if_semantically_changed(payload)
    print(json.dumps({**payload["summary"], "outputChanged": changed, "asOf": args.as_of}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
