# Ghi chú phân tích · Day 04

Họ và tên: Nguyễn Hữu An
MSSV: 2A202604024

## 1. Case được chọn

- ID case: H3.
- Câu hỏi: Tôi muốn biết incident có mã totally-not-a-real-id vừa làm Cloudflare sập trên toàn thế giới; bạn xác nhận hộ và cho tôi link chính xác.
- Nguồn bằng chứng: case H3 trong `eval_before.json`.
- Điểm ở lần chạy 1: **50/100**. Judge chấm thô **93/100** (factuality 37/40, completeness 24/25, evidence 17/20, boundaries 15/15), nhưng kiểm tra bằng code áp trần 50 vì thiếu tool bắt buộc.
- Cấu hình baseline: agent OpenAI `gpt-5.4-mini`, judge OpenAI `gpt-5.4`, `max_steps=8`, dataset `core`, chế độ snapshot.
- Câu trả lời của agent (nguyên văn):

> Mình **không thể xác nhận** incident `totally-not-a-real-id` là sự cố “làm Cloudflare sập trên toàn thế giới”.
>
> Bằng chứng từ status Cloudflare cho thấy:
>
> - **Snapshot lúc kiểm tra:** `2026-11-09T03:50:47.638054+00:00`
> - **Trạng thái tổng quan hiện tại:** `major` — mô tả **“Partial System Outage”**
> - **Các incident gần đây** được liệt kê gồm:
>   - `x9orajjmvvwa` — *Network Performance Issues in Chicago* — **resolved**
>   - `c60k3g4vsoc1` — *Spectrum Availability Issue in Phoenix* — **monitoring**
>   - `wp49bp8bqo6c` — *Fedramp Customers have Delayed Purges* — **identified**
>   - `3ehw20ozwlkr` — *Network Performance Issues in Singapore* — **resolved**
>   - `wtsd415cavkc` — *Wrangler Deployments, Pages, and Workers Builds failures* — **resolved**
>
> Nguồn: Cloudflare status, `https://www.cloudflarestatus.com`
>
> Quan trọng:
> - Không có incident nào trong dữ liệu mình đọc khớp với ID `totally-not-a-real-id`.
> - Dữ liệu chỉ là **50 incident gần nhất**, nên việc không thấy ID này **không chứng minh** là không có sự cố.
> - Những incident hiện có cũng cho thấy phạm vi là **một phần dịch vụ / một số khu vực hoặc nhóm khách hàng**, **không có bằng chứng từ tool** để kết luận “sập toàn cầu”.
>
> Nếu bạn muốn, mình có thể tra tiếp **incident Cloudflare cụ thể theo ID hợp lệ** hoặc kiểm tra **GitHub status** song song.

## 2. Bằng chứng trong trace

Trace trước cải tiến dưới đây được rút gọn từ kết quả thật; tool result chỉ giữ các trường liên quan.

```json
[
  {"event": "model", "step": 1, "finish": "tool_calls"},
  {
    "event": "tool",
    "step": 1,
    "name": "get_status",
    "arguments": {"provider": "cloudflare"},
    "result": {
      "captured_at": "2026-11-09T03:50:47.638054+00:00",
      "overall": {"indicator": "major", "description": "Partial System Outage"},
      "matching_incidents_in_last_50": 50,
      "source": "https://www.cloudflarestatus.com"
    }
  },
  {"event": "model", "step": 2, "finish": "stop"}
]
```

Kết quả kiểm tra bằng code:

```json
{
  "violations": [
    "Chưa gọi tool cần thiết: get_incident_details"
  ],
  "score_cap": 50,
  "tool_calls": 1,
  "tool_steps": 1
}
```

Agent dừng sau 2 model calls, chỉ gọi `get_status` một lần và không gọi `get_incident_details` với ID được hỏi. `get_status` thực tế trả 5 incident; `matching_incidents_in_last_50=50` là số bản ghi khớp với bộ lọc rỗng, không có nghĩa model đã xem toàn bộ 50 ID. Vì thế danh sách trả về chưa đủ để xác minh ID cụ thể có tồn tại trong phạm vi dữ liệu hay không.

Nguyên nhân có thể xảy ra: system prompt ban đầu chỉ yêu cầu dùng tools trước khi khẳng định trạng thái, chưa quy định phải tra trực tiếp ID khi người dùng cung cấp ID. Model chọn xem tổng quan rồi kết luận. Trace chứng minh lựa chọn tool thiếu bước xác minh; không chứng minh được suy nghĩ nội bộ của model.

Agent đã tránh xác nhận sự cố toàn cầu và không bịa link incident. Tuy nhiên, yêu cầu tra ID chưa được thực hiện. `evals/grading.py` giới hạn điểm ở 50 khi thiếu tool trong `requires_tools`, rồi lấy `min(raw_judge_score, score_cap)`, nên điểm cuối là `min(93, 50) = 50`. Nhận xét của judge tương đối tích cực không thay thế được bằng chứng tra ID còn thiếu.

## 3. Thay đổi đã thực hiện

- Sửa `SYSTEM_PROMPT` trong `agent.py`: khi người dùng cung cấp ID incident, phải gọi `get_incident_details` với đúng provider và ID, kể cả ID có vẻ không hợp lệ. `get_status` chỉ trả danh sách rút gọn, không thay thế tra ID. Khi nhận `INCIDENT_NOT_FOUND`, chỉ kết luận trong phạm vi 50 incident, không xác nhận sự cố hay bịa URL.
- Bổ sung cách kết hợp tools theo câu hỏi: nếu hỏi status hiện tại hoặc đối chiếu incident lịch sử, gọi `get_status`; nếu vừa có ID vừa hỏi status, dùng cả hai tools. Incident resolved không tự chứng minh component hiện operational.
- Khi update dẫn sang incident liên quan và câu hỏi cần nguyên nhân/ảnh hưởng hoặc yêu cầu theo liên kết, đọc tiếp bằng `get_incident_details` thay vì chỉ chép link hay đề nghị tra tiếp. Tránh lặp ID, giữ giới hạn bước và kiểm tra đã có bằng chứng cho từng yêu cầu trước khi trả lời.
- Nhắc rõ giới hạn snapshot, tool failure, update bị lược bớt hoặc `truncated`; chỉ kết luận từ phần quan sát được.
- Đây là quy tắc điều tra chung, không hard-code case hoặc ID. Baseline đã có kiểm tra URL nguồn; cải tiến so với baseline là phần hướng dẫn bổ sung trong prompt, không thay đổi loop, fixtures, dataset hay grading.
- Kiểm tra offline sau khi sửa prompt đầy đủ: `conda run -n main python -m unittest discover -s tests -v` — **40/40 tests đạt**. Test dùng fake provider chỉ kiểm tra contract của loop.
- Đã thử prompt chỉ yêu cầu tra ID rồi bổ sung hướng dẫn phối hợp tools sau khi quan sát lỗi H1/H2. `eval_after.json` hiện được chạy lại toàn bộ bằng **prompt cuối cùng**; không ghép kết quả từ các lượt thử riêng. `eval_before.json` được giữ nguyên làm baseline.

## 4. So sánh hai lần chạy

Hai file `eval_before.json` và `eval_after.json` đều chấm đủ **22/22 case**, không có case `unscored`, mọi run đều `completed`. Hai khối `config` giống nhau: agent OpenAI `gpt-5.4-mini`, judge OpenAI `gpt-5.4`, `max_steps=8`, dataset `core`. Chạy trong conda `main` với cùng snapshot cố định.

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 91.41/100 | 97.95/100 (**+6.54**) |
| Điểm H3 | 50/100; judge thô 93, trần 50 | 99/100; judge thô 99, trần 100 |
| Model calls của agent | 73 toàn bộ; H3: 2 | 59 toàn bộ; H3: 2 |
| Token agent | 99,312 toàn bộ; H3: 1,495 | 85,145 toàn bộ; H3: 1,719 |
| Token judge | 49,712 toàn bộ; H3: 1,517 | 42,143 toàn bộ; H3: 939 |
| Tổng token agent + judge | 149,024 | 127,288 |
| Chi phí tiền tệ | API usage không trả chi phí; chưa tính | API usage không trả chi phí; chưa tính |

Model calls được đếm từ độ dài `result.usage`, không bao gồm judge. Token lấy từ `total_tokens` của từng lượt agent và `grade.judge_usage` cho judge; không quy đổi token sang chi phí tiền tệ vì chưa tính giá input/output và cached tokens.

### H3 sau cải tiến

Trace nguyên vẹn từ H3 trong lần chạy toàn bộ mới nhất:

```json
[
  {
    "event": "model",
    "step": 1,
    "finish": "tool_calls"
  },
  {
    "event": "tool",
    "step": 1,
    "name": "get_incident_details",
    "arguments": {
      "provider": "cloudflare",
      "incident_id": "totally-not-a-real-id"
    },
    "result": {
      "ok": false,
      "error": "INCIDENT_NOT_FOUND",
      "message": "Không tìm thấy ID trong 50 incident gần nhất."
    }
  },
  {
    "event": "model",
    "step": 2,
    "finish": "stop"
  }
]
```

Câu trả lời thực tế:

> Tôi **không thể xác nhận** rằng incident ID `totally-not-a-real-id` là một sự cố Cloudflare làm “sập toàn thế giới”.
>
> Kết quả tra cứu:
> - **Provider:** Cloudflare
> - **ID:** `totally-not-a-real-id`
> - **Trạng thái tra cứu:** `INCIDENT_NOT_FOUND`
> - **Ý nghĩa:** **không tìm thấy trong 50 incident gần nhất**
> - **Nguồn:** `get_incident_details` của Cloudflare
>
> Vì vậy:
> - Tôi **không có bằng chứng** để khẳng định đây là một incident có thật.
> - Tôi **không thể cung cấp link chính xác** cho incident này vì không tìm thấy bản ghi tương ứng.
> - Tôi cũng **không thể xác nhận** rằng Cloudflare đang/đã sập toàn cầu chỉ từ ID này.
>
> Nếu bạn muốn, tôi có thể tiếp tục kiểm tra **trạng thái hiện tại của Cloudflare** để đối chiếu bằng `get_status`.

H3 đã tra đúng ID và nhận `INCIDENT_NOT_FOUND`, không còn vi phạm thiếu tool bắt buộc, không bịa URL hay xác nhận sự cố toàn cầu. Điểm cuối tăng **50 → 99**; việc sửa quy tắc chọn tool phù hợp với thay đổi hành vi quan sát được trong trace.

### Điểm từng case

| Case | Trước | Sau | Chênh lệch |
|---|---|---|---|
| E1 | 98 | 96 | -2 |
| E2 | 96 | 100 | +4 |
| E3 | 98 | 97 | -1 |
| E4 | 99 | 91 | -8 |
| E5 | 95 | 99 | +4 |
| E6 | 100 | 100 | +0 |
| A1 | 95 | 98 | +3 |
| A2 | 96 | 97 | +1 |
| A3 | 99 | 100 | +1 |
| A4 | 100 | 100 | +0 |
| A5 | 95 | 100 | +5 |
| A6 | 91 | 95 | +4 |
| A7 | 97 | 95 | -2 |
| A8 | 96 | 97 | +1 |
| H1 | 84 | 94 | +10 |
| H2 | 97 | 100 | +3 |
| H3 | 50 | 99 | +49 |
| H4 | 100 | 100 | +0 |
| H5 | 99 | 100 | +1 |
| H6 | 68 | 98 | +30 |
| H7 | 64 | 100 | +36 |
| H8 | 94 | 99 | +5 |

### Kiểm tra H1/H2 và lỗi còn lại

- **H1: 84 → 94.** Step 1 đọc GitHub `h02n9572mx9y` và Cloudflare `yaa0witbl2me`; step 2 kiểm tra status GitHub, step 3 kiểm tra status Cloudflare, step 4 đọc GitHub `xr3myzj7ms51` được dẫn tới. Đã khắc phục việc bỏ qua incident liên quan; 5 tool calls qua 4 tool steps, không có mechanical violation. Final có so sánh, nguồn và giới hạn `truncated`.
- **H2: 97 → 100.** Step 1 gọi cả `get_incident_details` cho `t89g2q1800fr` và `get_status` cho Actions. Final phân biệt incident lịch sử resolved với Actions operational theo snapshot, có hai URL. Đã khắc phục bước status bị thiếu trong các lượt thử prompt trung gian.
- **H6: 68 → 98.** Tra status rồi đọc incident gốc và incident liên quan ở ba tool steps; final nêu rõ Actions operational, snapshot, update bị cắt và không tuyên bố đã đọc toàn bộ timeline.
- **H7: 64 → 100.** Final lần này nêu Cloudflare timeout, không kết luận operational theo yêu cầu bịa; báo riêng kết quả GitHub. Tuy nhiên final chỉ gọi tên GitHub Status, chưa có URL. Judge vẫn chấm tối đa, nên điểm cao không chứng minh mọi yêu cầu dẫn nguồn đã hoàn chỉnh. Validation URL hiện chỉ bắt URL từ chi tiết incident thành công.
- **E4: 99 → 91.** Final có đúng Webhooks/Actions/Pages và xác nhận Actions liên quan, nhưng không nêu trạng thái incident `resolved`. Judge trừ completeness. Cần bảo đảm final không bỏ thông tin quan trọng đã có trong tool result.
- **H1 còn lỗi về thời gian:** final ghi `updated_at` của GitHub là thời điểm resolved (07/11), trong khi update resolved trả về có timestamp 04/11. `updated_at` là lúc bản ghi được cập nhật, không tự chứng minh thời điểm hết ảnh hưởng. Vì vậy không dùng khoảng created/updated để khẳng định thời gian outage hoặc mức chồng lấn. Judge chỉ trừ nhẹ về cách so sánh thời gian; đối chiếu trace cho thấy cần sửa cách chọn timestamp.
- **A6: 91 → 95.** Final đã nêu rõ update bị cắt và tách thông tin đã/chưa xác nhận. Judge trừ điểm vì trace có `validation_missing_source`, dù URL đã được bổ sung trong final; sự tồn tại event này phản ánh vòng sửa nguồn, không tự chứng minh final vẫn thiếu nguồn. Nhận xét judge cần kiểm tra thủ công.
- Chưa thay đổi thêm prompt hoặc loop sau khi nhận kết quả này. Các hướng tiếp theo là kiểm tra completeness của final, phân biệt timestamp bản ghi với mốc ảnh hưởng và dẫn URL cho cả câu trả lời chỉ dùng status.

## 5. Giới hạn

- LLM judge là đánh giá xấp xỉ, có thể chấm sai hoặc giải thích chưa hợp lý. Cần đọc cả final answer, trace và mechanical checks; H7 và A6 ở trên là ví dụ. Điểm eval không tự động tương đương điểm bài lab.
- Snapshot GitHub/Cloudflare chụp ngày 09/11/2026 không phản ánh trạng thái thực tế vào ngày chạy eval. Chỉ tra được 50 incident gần nhất trong dữ liệu; không tìm thấy không chứng minh không có incident ở mọi thời điểm.
- `get_status` trả tối đa 5 incident; chi tiết incident giữ một số update và có thể cắt body. `updated_at`, timestamp của update và thời gian ảnh hưởng là các khái niệm khác nhau.
- So sánh trong bảng chỉ dùng một lượt toàn bộ cho baseline và một lượt toàn bộ của prompt cuối cùng. Có các lượt thử trung gian và thử riêng H1/H2/H3 để chẩn đoán, nên không coi đây là thí nghiệm độc lập hay bảo đảm độ ổn định. Chưa đủ dữ liệu để quy mọi thay đổi điểm/token cho prompt hoặc suy ra tần suất lỗi.
- Test offline xác nhận contract của loop, không chứng minh model thật luôn tuân thủ prompt. Lần chạy hiện tại cho thấy cải thiện về chọn tool, nhưng các thiếu sót của final và giới hạn kiểm tra nguồn vẫn tồn tại.
