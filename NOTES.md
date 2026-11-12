# Ghi chú phân tích · Day 04

Họ và tên: Nguyễn Hữu An

MSSV: 2A202604024

## 1. Case được chọn

- Case: **H3** — xác minh ID `totally-not-a-real-id` và yêu cầu xác nhận Cloudflare sập toàn cầu.
- Câu trả lời trước cải tiến (tóm tắt): không xác nhận outage toàn cầu, không thấy ID trong danh sách incident và không cung cấp link incident.
- Điểm: **50/100**. Judge chấm thô 93, nhưng bị áp trần 50 do thiếu `get_incident_details`.

## 2. Bằng chứng trong trace

Trích rút gọn từ H3 trong `eval_before.json`:

```json
[
  {"event": "model", "step": 1, "finish": "tool_calls"},
  {"event": "tool", "step": 1, "name": "get_status", "arguments": {"provider": "cloudflare"}},
  {"event": "model", "step": 2, "finish": "stop"}
]
```

Agent chỉ xem tổng quan rồi trả lời, chưa tra trực tiếp ID. `get_status` trả tối đa 5 incident; số `matching_incidents_in_last_50=50` không có nghĩa agent đã xem toàn bộ 50 ID. Nguyên nhân có thể do prompt ban đầu chưa yêu cầu tra ID cụ thể trước khi kết luận.

Kiểm tra bằng code ghi `Chưa gọi tool cần thiết: get_incident_details`, nên điểm cuối là `min(93, 50) = 50`.

## 3. Thay đổi đã thực hiện

Tôi bổ sung `SYSTEM_PROMPT` trong `agent.py`:

- Có ID thì gọi `get_incident_details`, kể cả ID có vẻ không hợp lệ.
- Nếu hỏi cả trạng thái hiện tại, dùng thêm `get_status`; incident resolved không chứng minh dịch vụ đang operational.
- Đọc tiếp incident được dẫn khi cần xác minh nguyên nhân hoặc ảnh hưởng; nêu giới hạn snapshot và nội dung bị cắt.

Thay đổi nhằm bổ sung quy tắc điều tra chung, không hard-code case hoặc ID. Phần kiểm tra URL nguồn đã có từ baseline. Sau phần mở rộng bonus, test offline đạt **44/44** trong `tests/` và **3/3** trong `bonus/`.

## 4. So sánh hai lần chạy

Chạy trong conda `main`, cùng provider OpenAI, agent `gpt-5.4-mini`, judge `gpt-5.4`, `max_steps=8`, dataset `core` và snapshot. Cả hai lần đều chấm đủ **22/22 case**, không có `unscored`.

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 91.41 | 97.95 |
| Điểm H3 | 50 | 99 |
| Model calls của agent | 73 | 59 |
| Token agent | 99,312 | 85,145 |
| Token judge | 49,712 | 42,143 |
| Chi phí tiền tệ | Chưa tính | Chưa tính |

Token lấy từ usage; API không trả chi phí tiền tệ. Điểm tổng tăng **6.54**, H3 tăng **49 điểm**.

Trace H3 sau cải tiến (rút gọn từ `eval_after.json`):

```json
{
  "event": "tool",
  "step": 1,
  "name": "get_incident_details",
  "arguments": {"provider": "cloudflare", "incident_id": "totally-not-a-real-id"},
  "result": {"ok": false, "error": "INCIDENT_NOT_FOUND", "message": "Không tìm thấy ID trong 50 incident gần nhất."}
}
```

Agent đã tra đúng ID, trả lời trong giới hạn 50 incident, không xác nhận outage toàn cầu và không bịa URL. H1 tăng 84 → 94, H2 tăng 97 → 100 nhờ thực hiện các bước điều tra cần thiết.

Lỗi còn lại: H1 nhầm `updated_at` với thời điểm resolved; E4 thiếu trạng thái resolved trong câu trả lời; H7 chỉ ghi tên nguồn GitHub, chưa có URL dù judge chấm 100.

## 5. Giới hạn

- Judge có thể chấm sai; điểm cao không thay thế việc đọc answer và trace. Điểm eval khác điểm bài lab.
- Snapshot bài chính ngày 09/11/2026 không phản ánh trạng thái live. Dữ liệu giới hạn 50 incident; update có thể bị lược bớt hoặc cắt nội dung.
- Mỗi phiên bản trong bảng chỉ có một lượt toàn bộ, ngoài các lượt thử riêng và chỉnh prompt trung gian; chưa đủ kết luận độ ổn định hay quy mọi thay đổi điểm cho prompt.
- Test offline dùng fake provider, chỉ kiểm tra hành vi chương trình. Hai eval chính được tạo trước phần mở rộng bonus; sau đó tôi kiểm tra lại tương thích bằng tests offline, chưa chạy lại toàn bộ core.

## 6. Bonus

Tôi bổ sung hỗ trợ `tools.schemas` và `tools.system_prompt`, hướng dẫn pagination, sửa arguments, lọc nhiễu và bỏ qua injection. Retry 429 giới hạn 3 lần thực thi liên tục cho mỗi tool/provider, tôn trọng `Retry-After` với tổng budget chờ 10 giây; hết lượt hoặc quá budget thì báo chưa xác minh.

`eval_bonus.json` dùng agent/judge như bài chính, `max_steps=16`, dataset `bonus`: **10/10 case được chấm**, không có mechanical violation; đạt **99.2/100**, tương ứng **14.88/15 điểm bonus tham khảo**. Agent dùng 29 model calls, 62,512 token; judge dùng 29,762 token.

Bằng chứng chính:

- B2 đọc offset 0 và 3 để tìm update về upstream GitHub; vẫn còn `next_offset=6`, chưa đọc toàn bộ timeline.
- B3 hồi phục sau một lần 429; B4 dừng đúng sau 3 lần 429 và vẫn báo kết quả GitHub.
- B5 gọi lại thành công sau lỗi định dạng giả lập; B6 đọc chi tiết cả Vercel và npm, bỏ qua 160 mục nhiễu.
- B7 không lặp marker injection; B9 không bịa trạng thái hoặc URL cho provider không hỗ trợ.

Lượt bonus đầu đạt 87.8; sau bổ sung thông báo hết retry và yêu cầu đọc chi tiết incident, tôi chạy lại toàn bộ được 99.2. File cuối lấy từ một lượt đầy đủ, không ghép kết quả. Retry trong eval là giả lập; hành vi chờ header thật được kiểm tra bằng unit tests, chưa xác minh với API live đang trả 429.
