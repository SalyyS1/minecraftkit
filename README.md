# Salyyy Minecraft Kit

**Bộ công cụ hỗ trợ làm plugin Minecraft cho Codex và Claude — SalyVn / Salyyy.**

Minecraft Kit giúp bạn chọn đúng hướng khi làm plugin: RPG, Paper/Folia, packet, NMS, resource pack, Blockbench/model, shader, client-side và dialog. Wiki có hướng dẫn dễ đọc; API Explorer có sẵn dữ liệu để tra nhanh. Kit không thay thế việc test trên server thật, nhưng giúp bạn bắt đầu nhanh và ít sai hướng hơn.

## Cài nhanh

```powershell
npx minecraftkit install --target both
```

Chỉ cài cho một bên:

```powershell
npx minecraftkit install --target codex
npx minecraftkit install --target claude
```

Muốn dùng lệnh ở mọi thư mục:

```powershell
npm install -g minecraftkit
minecraftkit doctor
```

`doctor` kiểm tra Node, PowerShell, Python và trạng thái cài đặt. `update` cập nhật Kit. `commands` liệt kê các route `mc:*`.

## Dùng ở đâu?

- [Wiki chính](https://salyys1.github.io/minecraftkit/wiki.html): hướng dẫn, cách cài và tìm kiếm theo việc bạn muốn làm.
- [Ecosystem Atlas](https://salyys1.github.io/minecraftkit/ecosystem.html): nguồn tham khảo, phiên bản và nền tảng Minecraft.
- [RPG API Explorer](https://salyys1.github.io/minecraftkit/): tra API của các plugin RPG đã được tổng hợp.
- [npm package](https://www.npmjs.com/package/minecraftkit) · [GitHub Releases](https://github.com/SalyyS1/minecraftkit/releases)

## Các lệnh Claude

Claude có `/mc:build`, `/mc:core`, `/mc:rpg`, `/mc:shader`, `/mc:dialog`, `/mc:client`, `/mc:pack`, `/mc:model`, `/mc:protocol` và `/mc:nms`. Codex tự chọn skill phù hợp từ nội dung bạn yêu cầu.

Xem [NOTICE.md](NOTICE.md) trước khi phân phối lại nội dung có nguồn gốc từ bên thứ ba.
