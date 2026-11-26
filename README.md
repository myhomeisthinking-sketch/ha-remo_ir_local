# Remo IR Local

[日本語](#日本語) | [English](#english)

---

# 日本語

Nature Remo の **Local API** で赤外線リモコンの信号を学習し、Home Assistant の**ボタンエンティティ**として登録・管理するカスタムインテグレーションです。クラウドを経由せず、同じネットワーク内のRemoと直接通信します。

## 特長

- Remoに向けて押したリモコンの信号を取得し、`button.remolocal_...` として登録
- サイドバーの専用パネル（管理者のみ）で、登録・編集・削除
- RemoのIPアドレスの変更に、自動で追従（ARP）
- 削除するとき、そのボタンを参照している設定を一覧表示
- ボタンは、Remoごとのデバイスにまとまります
- エリアの指定に対応

## 前提

- Nature Remo（Local API に対応した機種）と Home Assistant が、同じネットワーク（同一セグメント）にあること
- IPアドレスの追従に `/proc/net/arp` を使うため、HAがホストネットワークで動作していること

## 動作確認環境

- インストール方法：Home Assistant OS
- Home Assistant Core：2026.11.2
- Supervisor：2026.11.0
- Operating System：18.4
- フロントエンド：20261028.6

## インストール

### HACS（カスタムリポジトリ）

1. HACS を開き、右上のメニューから「カスタムリポジトリ」を選びます。
2. リポジトリに `https://github.com/myhomeisthinking-sketch/ha-remo_ir_local` を、種類に「Integration」を指定して追加します。
3. HACS で「Remo IR Local」をダウンロードし、HAを再起動します。
4. 設定 → デバイスとサービス → 統合を追加 →「Remo IR Local」を選びます。
5. サイドバーに「Remo IR Local」（管理者のみ）が表示されます。

### 手動

1. `custom_components/remo_ir_local/` を、HAの `config/custom_components/` にコピーします。
2. HAを再起動します。
3. 設定 → デバイスとサービス → 統合を追加 →「Remo IR Local」を選びます。
4. サイドバーに「Remo IR Local」（管理者のみ）が表示されます。

## 使い方

1. **Remoを追加**：mDNSで見えるRemo名（`Remo-XXXXXX`）から選び、表示名を付けます。IPはARPから自動で特定します。一覧に出ないときは「一覧に出ない場合（手入力）」を開き、識別子やIPを入力します（入力の組み合わせごとの動作は、画面に説明があります）。
2. **信号を取得**：①リモコンをRemoに向けて押します（認識すると青く光ります）→ ②すぐに「取得する」を押します。Remoは直近の1件しか保持しないので、複数の信号を登録するときも、この順で1件ずつ行います。
3. **ボタンを追加**：未登録の信号なら、`button.remolocal_` に続けてIDを入力し、アクション名称・アイコン・エリア（任意）を付けて追加します。
4. **登録済みのボタン**：送信 / 編集（名称・アイコン・エリア・Remo・信号の差し替え） / 削除ができます。削除するときは、そのボタンを参照している設定を表示し、ボタンのエンティティも、あわせて削除します。

## ボタンとして使う

登録した信号は、ダッシュボードに置いたり、automation や script から押したりできます。

```yaml
- action: button.press
  target:
    entity_id: button.remolocal_tv_power
```

- エンティティIDは、登録時に指定したものになります。後から変更するときは、HAの「設定 → デバイスとサービス → エンティティ」で行ってください（登録内容は内部の識別子で管理しているため、影響しません）。
- エリアは、ボタンのエンティティのエリアとして設定されます。HAの画面で変更した場合も、パネルは現在のエリアを表示します。パネルの編集で、解除もできます。
- `button.press` は、値を渡せません。実行のたびに値を変える場合は、`remo_ir_local.send` サービスを直接呼んでください。
- 複数の操作を続けて行う場合は、script や automation の中で `button.press` を順に呼びます。
- 登録内容は、統合の保存領域（`.storage/remo_ir_local`）に保存されます。

## IPアドレスの追従（ARP）

- **起動時**：最後に確認したIPをARPで検証し、一致しないRemoの分だけ、サブネットを走査します。
- **定期チェック**（既定5分、統合のオプションで変更可）：同様に整合性を確認し、変化・消失を通知します。
- **「再読込」ボタン**：全Remoを走査してIPを更新します（下の間引きは無視します）。
- **送信・取得が接続エラーのとき**：そのRemoだけ再解決して、1回再試行します（直前に見つからなかったRemoは、60秒間は走査し直さず、すぐ失敗にします）。
- **見つからないRemoの走査の間引き**：識別子の入力ミスなどで見つからない状態が続くRemoは、全体走査の間隔を 5分→10分→20分→…と空け、上限は60分です。最後のIPが分かっているRemoの確認（1台への接続確認）は軽いので、毎回行います。見つかると、間隔は元に戻ります。
- 登録時に見つからなかったときは、警告を表示します（登録は残ります。「再読込」で再試行でき、間違っていれば「設定」から削除できます）。

## サービス

- `remo_ir_local.send`（`remo`、`payload`）：台帳のRemoへ、赤外線信号を送信します。
- `remo_ir_local.refresh`：ARPを走査して、RemoのIPアドレスを更新します。

## 注意

- 同じ信号かどうかは、同じRemo上で、各要素が ±15%（下限50µs）以内かどうかで判定します。
- 削除時の参照検索は、automations.yaml / scenes.yaml / scripts.yaml / configuration.yaml / ダッシュボード（Lovelace）の保存データが対象です。ダッシュボードのカードなど、検出できない場所もあります。

## セキュリティ

- パネルとAPIは、管理者のみが使えます（サーバー側でも、管理者かどうかを確認します）。
- Remoとの通信（Local API）は、機器の仕様上、暗号化されない平文のHTTPです。ローカルネットワーク（プライベートアドレス）以外のIPアドレスへは、接続しません。手入力のIPも、同じ条件で検証します。
- Remoの識別とIPアドレスの追従は、ARPテーブルを利用します。同じネットワークに、信頼できない機器がいる環境では、なりすましの可能性があります。信頼できるネットワークで使ってください。
- Remoの応答は、サイズと内容を検証してから使い、画面に表示する値は、すべてエスケープします。
- サービス（`remo_ir_local.send`、`remo_ir_local.refresh`）は、HAの権限の仕組みに従い、管理者以外のユーザーからも呼び出せます。`refresh` は、連続して呼んでも、10秒に1回しか走査しません。
- 保存ファイル（`.storage/remo_ir_local`）は、所有者だけが読める権限で保存されます。

## ライセンス

MIT License です。詳細は、[LICENSE](LICENSE) を参照してください。

同梱のアイコン・ロゴ画像（`custom_components/.../brand/`）には、Nature Remo の商標が含まれます。これらの画像は、MITライセンスの対象外です。

## 免責事項

本プロジェクトは、Nature Remo の提供元とは無関係の、非公式なものです。「Nature Remo」は、その提供元の商標です。

---

# English

This custom integration learns infrared remote control signals using the **Nature Remo Local API** and registers and manages them as **button entities** in Home Assistant. It communicates directly with Nature Remo devices on the same network without using the cloud.

## Features

- Captures remote control signals sent toward a Nature Remo device and registers them as `button.remolocal_...` entities.
- Provides a dedicated sidebar panel (administrators only) for adding, editing, and deleting buttons.
- Automatically detects changes to Nature Remo IP addresses using ARP.
- Displays a list of configurations that reference a button before deleting it.
- Groups buttons into devices based on their associated Nature Remo units.
- Supports area assignment.

## Requirements

- Nature Remo (a model that supports the Local API) and Home Assistant must be on the same network (same subnet).
- Home Assistant must run in host network mode because `/proc/net/arp` is used to track IP address changes.

## Tested Environment

- Installation method: Home Assistant OS
- Home Assistant Core: 2026.11.2
- Supervisor: 2026.11.0
- Operating System: 18.4
- Frontend: 20261028.6

## Installation

### HACS (Custom Repository)

1. Open HACS and select **Custom repositories** from the menu in the upper-right corner.
2. Add `https://github.com/myhomeisthinking-sketch/ha-remo_ir_local` as a repository and select **Integration** as the category.
3. Download **Remo IR Local** through HACS and restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and select **Remo IR Local**.
5. **Remo IR Local** will appear in the sidebar (administrators only).

### Manual Installation

1. Copy `custom_components/remo_ir_local/` into `config/custom_components/` in your Home Assistant configuration directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and select **Remo IR Local**.
4. **Remo IR Local** will appear in the sidebar (administrators only).

## Usage

1. **Add a Remo**: Select a Remo device discovered via mDNS (for example, `Remo-XXXXXX`) and assign it a display name. Its IP address is detected automatically using ARP. If the device does not appear in the list, open **Not listed? (Manual Entry)** and enter its identifier or IP address. The UI explains the behavior of each input combination.
2. **Capture a Signal**:  
   ① Point your remote at the Remo and press a button (the Remo lights up blue when it recognizes the signal).  
   ② Immediately press **Capture**.  
   The Remo stores only the most recently received signal, so capture signals one at a time using this sequence.
3. **Add a Button**: If the signal has not already been registered, enter an ID after `button.remolocal_` and assign an action name, icon, and optionally an area.
4. **Manage Registered Buttons**: You can send signals, edit buttons (change the name, icon, area, associated Remo device, or assigned signal), and delete buttons. Before deletion, the integration displays a list of configurations referencing the button and also removes the corresponding button entity.

## Using Buttons

Registered signals can be added to dashboards or pressed from automations and scripts.

```yaml
- action: button.press
  target:
    entity_id: button.remolocal_tv_power
```

- The entity ID is the one specified during registration. To change it later, use **Settings → Devices & Services → Entities** in Home Assistant. This does not affect the integration's internal management, as registered items are identified using internal identifiers.
- The assigned area is set as the button entity's area. If you change the area through the Home Assistant interface, the panel will display the currently assigned area. You can also clear the area through the panel's edit function.
- `button.press` does not accept parameters. If you need to change the signal dynamically each time, call the `remo_ir_local.send` service directly.
- To perform multiple operations in sequence, call `button.press` for each button in a script or automation.
- Registered configurations are stored in the integration's storage directory (`.storage/remo_ir_local`).

## IP Address Tracking (ARP)

- **At startup**: The integration verifies the last known IP address using ARP. It scans the subnet only for Remo devices whose IP addresses do not match.
- **Periodic checks** (every 5 minutes by default; configurable through integration options): The integration performs the same consistency checks and reports changes or devices that are no longer found.
- **Reload button**: Scans for all registered Remo devices and updates their IP addresses, ignoring the scan backoff described below.
- **Connection errors during signal sending or capture**: The integration attempts to resolve the IP address of the affected Remo device again and retries once. If the device was not found recently, it skips another scan for 60 seconds and fails immediately.
- **Scan backoff for undiscovered Remo devices**: If a Remo device cannot be found repeatedly, for example due to an incorrect identifier, the interval between full subnet scans increases from 5 minutes to 10 minutes, 20 minutes, and so on, up to a maximum of 60 minutes. Checking the last known IP address (a connection check to a single device) is lightweight and is performed every time. Once the device is found, the interval returns to its default.
- If a Remo device cannot be found during registration, a warning is displayed. The registration is retained. You can retry using **Reload**, or remove the device through **Settings** if the information is incorrect.

## Services

- `remo_ir_local.send` (`remo`, `payload`): Sends an infrared signal to the specified Remo device in the registry.
- `remo_ir_local.refresh`: Scans the ARP table and updates the IP addresses of registered Remo devices.

## Notes

- Two signals are considered identical if every element is within ±15% of the corresponding value on the same Remo device, with a minimum tolerance of 50 µs.
- Reference checks performed before deletion cover `automations.yaml`, `scenes.yaml`, `scripts.yaml`, `configuration.yaml`, and saved dashboard (Lovelace) data. Some references, such as those in dashboard cards, may not be detected.

## Security

- The panel and its API are accessible to administrators only. Administrator privileges are also verified on the server side.
- Communication with Remo devices through the Local API uses unencrypted plain HTTP, as required by the device specifications. The integration does not connect to IP addresses outside the local network (private address ranges). Manually entered IP addresses are validated under the same conditions.
- ARP tables are used to identify Remo devices and track their IP addresses. On networks containing untrusted devices, ARP spoofing may be possible. Use this integration only on a trusted network.
- Responses from Remo devices are validated for size and content before being processed. All values displayed in the UI are properly escaped.
- The services (`remo_ir_local.send` and `remo_ir_local.refresh`) follow Home Assistant's permission system and can also be called by non-administrator users. Repeated calls to `refresh` are rate-limited to one scan every 10 seconds.
- The storage file (`.storage/remo_ir_local`) is saved with permissions that allow only its owner to read it.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

The bundled icon and logo images (`custom_components/.../brand/`) contain Nature Remo trademarks. These images are not covered by the MIT License.

## Disclaimer

This is an unofficial project and is not affiliated with the provider of Nature Remo. "Nature Remo" is a trademark of its respective owner.