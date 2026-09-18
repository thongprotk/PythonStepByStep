# Thực hành Kubernetes với dự án PY (FastAPI) — Hướng dẫn đầy đủ cho macOS

Tài liệu này để bạn thực hành lại **toàn bộ** trên máy Mac ở nhà, từ cài đặt công cụ tới deploy,
cập nhật, và các bài tập nâng cao. Dự án là app FastAPI (`app/main.py`), có endpoint `/health`,
`/predict` (sklearn), `/chat` (gọi Anthropic API).

> **Vì sao dùng `kind` trên Mac chứ không phải `kubeadm`?**
> Ở máy Linux văn phòng bạn đã dựng cluster bằng `kubeadm` (control-plane thật, chạy trực tiếp trên
> kernel Linux). `kubeadm` **cần chạy trên Linux thật** (kubelet thao tác trực tiếp với cgroups,
> iptables, kernel modules của máy host). macOS không có các thứ này native, nên `kubeadm` không thể
> chạy thẳng trên Mac — muốn dùng vẫn phải tạo 1 VM Linux trước (phức tạp, không cần thiết để học).
> Trên Mac, cách chuẩn và được cộng đồng dùng nhiều nhất để có cluster K8s local là **`kind`**
> (Kubernetes IN Docker — mỗi "node" là 1 container Docker) hoặc **Docker Desktop's built-in
> Kubernetes**. Tài liệu này dùng `kind` làm hướng chính vì gần với thực hành ở máy Linux hơn (cùng
> `kubectl apply`, cùng file YAML) và cho phép multi-node/đổi CNI (mục 9.5) — nhưng nếu bạn muốn bắt
> đầu nhanh nhất, ít bước cài đặt nhất, xem **mục 1.6** để dùng luôn Kubernetes có sẵn trong Docker
> Desktop mà bạn đã cài — không cần cài `kind` và không cần bước nạp image thủ công.

---

## Mục lục

1. [Chuẩn bị & cài đặt công cụ](#1-chuẩn-bị--cài-đặt-công-cụ)
2. [Tổng quan project & Dockerfile](#2-tổng-quan-project--dockerfile)
3. [Build image & tạo cluster](#3-build-image--tạo-cluster)
4. [Giải thích từng file YAML cơ bản](#4-giải-thích-từng-file-yaml-cơ-bản)
5. [Deploy & kiểm tra](#5-deploy--kiểm-tra)
6. [Thực hành cập nhật (update/rollback/scale)](#6-thực-hành-cập-nhật-updaterollbackscale)
7. [Dọn dẹp](#7-dọn-dẹp)
8. [Cải tiến tiếp theo & giải thích](#8-cải-tiến-tiếp-theo--giải-thích)
9. [Các file YAML nâng cao để học sâu hơn](#9-các-file-yaml-nâng-cao-để-học-sâu-hơn)
10. [Troubleshooting thường gặp](#10-troubleshooting-thường-gặp)

---

## 1. Chuẩn bị & cài đặt công cụ

### 1.1. Homebrew (nếu chưa có)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Homebrew là package manager cho macOS — dùng để cài mọi công cụ CLI bên dưới thay vì tải thủ công.

### 1.2. Docker Desktop
Tải và cài từ trang chủ Docker (chọn bản Apple Silicon hoặc Intel tùy máy), mở app 1 lần để nó khởi
động daemon nền. `kind` **bắt buộc** cần Docker (hoặc Podman) đang chạy, vì mỗi "node" K8s của `kind`
thực chất là 1 container Docker.

Kiểm tra:
```bash
docker version
docker ps
```

### 1.3. kubectl — CLI để giao tiếp với API server của K8s
```bash
brew install kubectl
kubectl version --client
```
`kubectl` không tự chứa cluster — nó chỉ là client gửi request tới API server (giống `psql` là
client, không phải chính Postgres).

### 1.4. kind — công cụ tạo cluster K8s chạy trong Docker
```bash
brew install kind
kind version
```

### 1.5. Helm (dùng ở bài nâng cao, mục 8)
```bash
brew install helm
helm version
```

### 1.6. (Tuỳ chọn — cách nhanh nhất) Bật Kubernetes có sẵn trong Docker Desktop
Không cần cài thêm gì — Docker Desktop đã đóng gói sẵn 1 cluster K8s 1-node:

1. Mở Docker Desktop → **Settings** (biểu tượng bánh răng) → **Kubernetes**.
2. Tick **Enable Kubernetes** → **Apply & Restart** (lần đầu sẽ tải thêm vài image, mất 1–2 phút).
3. Kiểm tra:
   ```bash
   kubectl config get-contexts       # sẽ thấy context "docker-desktop"
   kubectl config use-context docker-desktop
   kubectl get nodes                 # 1 node, STATUS = Ready
   ```

Khác biệt quan trọng so với `kind` khi thực hành ở mục 3 và 6: vì Docker Desktop's Kubernetes dùng
**chung** Docker daemon với lệnh `docker build` bạn chạy tay, image build xong là cluster **thấy
ngay lập tức** — bỏ hẳn bước `kind create cluster` và `kind load docker-image`. Cứ `docker build`
rồi `kubectl apply -f k8s/` là chạy được. Khi cần chuyển qua lại giữa 2 cluster (nếu bạn cài cả
`kind` lẫn bật Docker Desktop's Kubernetes), dùng `kubectl config get-contexts` /
`kubectl config use-context <tên>` để chọn đúng cluster đang muốn thao tác.

Đánh đổi: cluster này luôn chỉ có 1 node, không tạo/xoá nhanh như `kind delete cluster`, và mục 9.5
(đổi CNI sang Calico để NetworkPolicy có tác dụng) **không áp dụng được** — muốn học phần đó vẫn cần
quay lại `kind`.

---

## 2. Tổng quan project & Dockerfile

Cấu trúc liên quan:
```
PY/
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py          # tạo FastAPI app, include các router, lifespan seed demo model
│   ├── core/config.py   # đọc biến môi trường (APP_NAME, DEBUG, DATABASE_URL, ANTHROPIC_API_KEY, CHAT_MODEL, LLM_TIMEOUT, MODEL_PATH)
│   ├── api/routes/      # health.py, predict.py (+/train), chat.py, cv.py
│   ├── ml/model.py      # LinearRegression (sklearn) + save/load joblib
│   ├── cv/processor.py  # to_grayscale + encode_png (OpenCV)
│   └── llm/client.py    # gọi Anthropic API (mặc định claude-3-5-sonnet-latest)
├── tests/
└── k8s/
    ├── configmap.yaml
    ├── secret.yaml
    ├── deployment.yaml
    ├── service.yaml
    └── advanced/        # xem mục 9
```

**Dockerfile hiện tại** (đã sửa 2 lỗi so với bản gốc: thiếu `COPY requirements.txt` trước khi
`pip install`, và cú pháp `gunicorn` sai flag — nay dùng thẳng `uvicorn` vì K8s scale bằng
**replicas** (nhiều pod), không cần multi-worker-process trong 1 container):
```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8888

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
```
Giải thích từng dòng:
- `FROM python:3.12-slim` — base image nhỏ gọn. Phải ≥3.10 vì code dùng syntax `X | None`
  (`app/ml/model.py`, `app/schemas/common.py`); bản 3.9 cũ crash ngay lúc import.
  Dùng `opencv-python-headless` (thay vì `opencv-python`) vì image slim thiếu `libGL` hệ thống.
- `WORKDIR /app` — mọi lệnh `COPY`/`RUN` sau đó chạy tương đối trong `/app` bên trong container.
- `COPY requirements.txt .` rồi mới `RUN pip install` (tách riêng bước này) — tận dụng **Docker layer
  cache**: nếu code app đổi nhưng `requirements.txt` không đổi, Docker sẽ tái sử dụng layer đã cài
  dependency, build nhanh hơn nhiều so với copy hết code trước.
- `COPY app/ ./app/` — chỉ copy code cần chạy, không copy `tests/`, `.git`, v.v.
- `EXPOSE 8888` — chỉ mang tính khai báo/tài liệu, không tự mở port; port thật sự mở là do
  `--port 8888` của uvicorn, và K8s Service sẽ trỏ vào đúng port này.
- `CMD [...]` — lệnh chạy khi container start. `app.main:app` nghĩa là: import module
  `app.main`, lấy biến `app` (instance `FastAPI()`).

---

## 3. Build image & tạo cluster

> **Dùng Docker Desktop's Kubernetes (mục 1.6)?** Chỉ cần chạy **3.1**, rồi bỏ qua thẳng 3.2 và 3.3
> — sang mục 5 (`kubectl apply -f k8s/`) luôn. Phần còn lại của tài liệu (mục 5 trở đi) áp dụng y hệt
> cho cả 2 cách, trừ 2 việc: (a) không có `kind` để `kind delete cluster` ở mục 7 — thay bằng tắt
> switch "Enable Kubernetes" trong Settings nếu muốn dọn sạch; (b) mục 9.5 (Calico/NetworkPolicy)
> chỉ làm được với `kind`.

### 3.1. Build Docker image
```bash
cd ~/PY   # hoặc đường dẫn bạn clone project trên Mac
docker build -t py-app:local .
```
- `-t py-app:local` — đặt tên (tag) cho image, dùng lại đúng tên này trong `deployment.yaml`
  (`image: py-app:local`).

### 3.2. Tạo cluster bằng kind
```bash
kind create cluster --name py-practice
```
Lệnh này: kéo image node K8s (nếu chưa có), khởi động 1 container Docker đóng vai trò node, cài đặt
control-plane bên trong, rồi **tự động** trỏ `~/.kube/config` sang context `kind-py-practice`.

Kiểm tra:
```bash
kubectl cluster-info --context kind-py-practice
kubectl get nodes
```

### 3.3. Nạp image vào cluster
`kind` không tự pull image `py-app:local` từ đâu cả (image này chỉ nằm trong Docker daemon của máy
bạn, không phải trên Docker Hub) — phải nạp thủ công vào node:
```bash
kind load docker-image py-app:local --name py-practice
```
Nếu bỏ qua bước này, pod sẽ báo lỗi `ErrImageNeverPull` hoặc `ImagePullBackOff` vì
`imagePullPolicy: IfNotPresent` không tìm thấy image trong node.

---

## 4. Giải thích từng file YAML cơ bản

### 4.1. `k8s/configmap.yaml` — cấu hình không nhạy cảm
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: py-app-config
data:
  APP_NAME: "PY Learning Project (k8s)"
  DEBUG: "false"
  DATABASE_URL: "sqlite:///./app.db"
```
Mục đích: tách cấu hình ra khỏi image — muốn đổi `APP_NAME` không cần build lại image, chỉ cần sửa
ConfigMap rồi restart pod. Dữ liệu ở đây **không mã hoá**, ai đọc được cluster cũng đọc được — vì vậy
không được để password/API key ở đây.

### 4.2. `k8s/secret.yaml` — cấu hình nhạy cảm
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: py-app-secret
type: Opaque
stringData:
  ANTHROPIC_API_KEY: ""
```
`Secret` giống `ConfigMap` về cách dùng, khác ở chỗ K8s lưu trữ dạng base64 (mặc định — **không phải
mã hoá thật**, chỉ là encode) và có thể bật thêm encryption-at-rest ở tầng etcd (nâng cao, không cần
cho bài học). `stringData` là field tiện dụng — bạn viết plain text, K8s tự encode base64 khi lưu
(khác với field `data` phải tự base64 tay).

⚠ Không commit key thật vào git. Cách dùng thực tế nên là:
```bash
kubectl create secret generic py-app-secret --from-literal=ANTHROPIC_API_KEY=sk-ant-xxx
```

### 4.3. `k8s/deployment.yaml` — quản lý vòng đời pod
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: py-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: py-app
  template:
    metadata:
      labels:
        app: py-app
    spec:
      containers:
        - name: py-app
          image: py-app:local
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8888
          envFrom:
            - configMapRef: { name: py-app-config }
            - secretRef: { name: py-app-secret }
          readinessProbe: {...}
          livenessProbe: {...}
          resources: {...}
```
Giải thích từng field:
- `replicas: 2` — luôn duy trì đúng 2 pod chạy app này. Xoá 1 pod thủ công, Deployment sẽ tự tạo pod
  mới thay thế ngay (self-healing) — đây là bài thực hành nên thử ở mục 6.
- `selector.matchLabels` — Deployment "quản lý" pod nào dựa vào label khớp với selector này, không
  phải dựa vào tên.
- `template` — khuôn mẫu để tạo pod mới; mỗi lần bạn sửa `template` (đổi image, đổi env...) và
  `kubectl apply`, Deployment sẽ tạo **rolling update** — thay pod cũ bằng pod mới lần lượt, không
  downtime (nếu cấu hình đúng).
- `imagePullPolicy: IfNotPresent` — dùng image có sẵn trong node nếu tìm thấy, không cố pull từ
  registry ngoài. Bắt buộc phải để vậy khi dùng image local nạp qua `kind load`.
- `envFrom.configMapRef` / `secretRef` — bơm **toàn bộ** key trong ConfigMap/Secret thành biến môi
  trường trong container (khác với `env.valueFrom` là chọn từng key một).
- `readinessProbe` — K8s gọi `GET /health` định kỳ; pod **chưa "Ready"** (chưa nhận traffic từ
  Service) cho tới khi probe này pass lần đầu. Dùng để tránh gửi request vào pod còn đang khởi động.
- `livenessProbe` — nếu probe này fail liên tục, K8s coi container "chết trong lúc chạy" (deadlock,
  treo...) và **restart container** đó (khác readiness — readiness fail chỉ rút traffic ra, không
  restart).
- `resources.requests` — lượng CPU/RAM tối thiểu pod cần để scheduler chọn node đủ chỗ đặt pod.
- `resources.limits` — mức trần; container vượt `limits.memory` sẽ bị kernel OOM-kill; vượt
  `limits.cpu` sẽ bị "throttle" (chậm lại) chứ không bị kill.

### 4.4. `k8s/service.yaml` — địa chỉ mạng ổn định cho tập hợp pod
```yaml
apiVersion: v1
kind: Service
metadata:
  name: py-app
spec:
  selector:
    app: py-app
  ports:
    - port: 8888
      targetPort: 8888
  type: ClusterIP
```
Pod có IP riêng nhưng **IP đó đổi mỗi lần pod bị tạo lại** (restart, rolling update...) — Service tạo
ra 1 tên DNS ổn định (`py-app`, hoặc đầy đủ `py-app.default.svc.cluster.local`) và tự động cân bằng
tải (round-robin) tới đúng các pod đang có label khớp `selector`, bất kể pod đó IP gì hay có bao
nhiêu pod. `type: ClusterIP` (mặc định) nghĩa là chỉ truy cập được **từ bên trong cluster** — vì vậy
cần `kubectl port-forward` để test từ máy Mac của bạn.

---

## 5. Deploy & kiểm tra

```bash
# Áp toàn bộ manifest cơ bản
kubectl apply -f k8s/

# Theo dõi pod được tạo
kubectl get pods -w
# Ctrl+C khi thấy STATUS = Running, READY = 1/1 cho cả 2 pod

# Xem chi tiết 1 pod (rất hữu ích khi debug — xem Events ở cuối output)
kubectl describe pod <tên-pod>

# Xem log real-time
kubectl logs -f deploy/py-app

# Vào bên trong 1 container để debug thủ công
kubectl exec -it deploy/py-app -- /bin/bash

# Forward port 8888 của Service ra máy Mac
kubectl port-forward svc/py-app 8888:8888
# Mở terminal khác:
curl localhost:8888/health
curl -X POST localhost:8888/predict -H "Content-Type: application/json" -d '{"features":[1,2]}'
```
Lưu ý app seed sẵn demo model lúc startup (`y = 2x0 + 3x1 + 1`) nên `/predict` với đúng 2
features chạy được ngay; muốn train model riêng thì gọi `POST /predict/train` (xem `AGENTS.md`).

---

## 6. Thực hành cập nhật (update/rollback/scale)

### 6.1. Self-healing — xoá pod xem K8s tự phục hồi
```bash
kubectl get pods
kubectl delete pod <tên-1-pod-bất-kỳ>
kubectl get pods -w   # thấy pod mới được tạo gần như ngay lập tức
```

### 6.2. Scale thủ công
```bash
kubectl scale deployment py-app --replicas=4
kubectl get pods
```

### 6.3. Đổi CODE (sửa file trong `app/`) — cần build lại image
Vì image được đóng gói (baked) sẵn code lúc `docker build`, sửa code xong **luôn luôn** phải build
lại rồi mới deploy — không có cách nào "hot reload" code vào pod đang chạy (đó là việc của môi
trường dev cục bộ, không phải K8s).

```bash
# 1. Sửa gì đó trong app/, ví dụ app/api/routes/health.py — đổi message trả về

# 2. Build lại image (cùng tag "local" — cố tình dùng tag cố định để bước dưới đơn giản)
docker build -t py-app:local .

# 3. CHỈ cần nếu bạn dùng kind (bỏ qua bước này nếu dùng Docker Desktop's Kubernetes — mục 1.6,
#    vì cluster đó dùng chung Docker daemon, thấy image mới ngay sau bước 2):
kind load docker-image py-app:local --name py-practice

# 4. Ép Deployment tạo lại pod dù tag image không đổi — K8s mặc định KHÔNG tự biết nội dung
#    đằng sau tag "local" đã đổi (chỉ so sánh chuỗi tag, không hash lại content mỗi lần apply)
kubectl rollout restart deployment py-app

# 5. Theo dõi tiến trình rolling update — pod cũ chỉ bị xoá sau khi pod mới Ready (readinessProbe
#    pass), nên nếu code mới bị lỗi ngay lúc khởi động, pod cũ vẫn tiếp tục nhận traffic, không downtime
kubectl rollout status deployment py-app
kubectl rollout history deployment py-app

# 6. Xác nhận bằng mắt là code mới đã chạy
kubectl port-forward svc/py-app 8888:8888 &
curl localhost:8888/health
```
> Mẹo: nếu muốn mỗi lần build ra tag khác nhau để dễ phân biệt version trong `kubectl rollout
> history` (thay vì luôn ghi đè `local`), đặt tag theo git commit — `docker build -t
> py-app:$(git rev-parse --short HEAD) .` — rồi sửa `image:` trong `deployment.yaml` sang tag đó
> trước khi `kubectl apply`. Cách này thì **không cần** `kubectl rollout restart` nữa, vì đổi
> `image:` trong manifest tự động kích hoạt rolling update.

### 6.4. Đổi ENV/cấu hình (`ConfigMap` hoặc `Secret`) — KHÔNG cần build lại image
Env chỉ được đọc **lúc container khởi động** (`pydantic-settings` đọc 1 lần lúc import
`get_settings()`), nên sửa ConfigMap/Secret xong vẫn phải cho pod khởi động lại — nhưng **không**
đụng gì tới Docker image cả, nhanh hơn hẳn so với đổi code:

```bash
# Ví dụ: đổi APP_NAME trong k8s/configmap.yaml, hoặc thêm ANTHROPIC_API_KEY thật vào k8s/secret.yaml

# 1. Áp lại đúng file vừa sửa (không cần build/load gì)
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# 2. Deployment KHÔNG tự biết ConfigMap/Secret bên trong nó tham chiếu vừa đổi nội dung
#    (envFrom không "watch" thay đổi) — phải tự kích hoạt restart:
kubectl rollout restart deployment py-app
kubectl rollout status deployment py-app

# 3. Xác nhận giá trị env mới đã vào đúng container
kubectl exec deploy/py-app -- printenv | grep -E 'APP_NAME|DEBUG|DATABASE_URL'
```
Cách nhanh hơn khi chỉ đổi 1-2 giá trị tạm thời để test (không sửa file YAML, không nên dùng lâu dài
vì mất khi pod bị xoá và không đồng bộ lại với git):
```bash
kubectl set env deployment/py-app DEBUG=true
kubectl set env deployment/py-app ANTHROPIC_API_KEY=sk-ant-xxx
```
Lệnh `set env` tự động trigger rolling update luôn, không cần `rollout restart` thêm.

### 6.5. Đổi CẢ CODE lẫn ENV cùng lúc
Gộp thứ tự của 6.3 và 6.4 — áp ConfigMap/Secret **trước**, build/load image **sau cùng**, để chỉ tốn
1 lần rolling update thay vì 2 lần:
```bash
kubectl apply -f k8s/configmap.yaml -f k8s/secret.yaml
docker build -t py-app:local .
kind load docker-image py-app:local --name py-practice   # bỏ qua nếu dùng Docker Desktop's K8s
kubectl rollout restart deployment py-app
kubectl rollout status deployment py-app
```

### 6.6. Rollback về version trước
```bash
kubectl rollout undo deployment py-app
```
Lưu ý quan trọng: `rollout undo` chỉ rollback lại **`template` của Deployment** (image tag, env
tham chiếu…) — nếu bản build trước dùng cùng tag `py-app:local` đã bị ghi đè bởi build mới, undo sẽ
không lấy lại được code cũ (vì Docker image `local` giờ đã là bản mới). Muốn rollback thật sự đáng
tin cậy, quay lại mẹo đặt tag theo git commit ở mục 6.3.

---

## 7. Dọn dẹp

```bash
kubectl delete -f k8s/          # xoá hết resource đã tạo, giữ cluster
kind delete cluster --name py-practice   # xoá luôn cluster (giải phóng container Docker)
```

---

## 8. Cải tiến tiếp theo & giải thích

Những điểm sau **chưa** cần làm ngay, nhưng là hướng cải tiến hợp lý khi đã quen bài cơ bản:

1. **Postgres thật thay vì sqlite mặc định** — `DATABASE_URL` hiện trỏ vào sqlite file trong
   container (dữ liệu **mất khi pod bị xoá**, vì không có volume). Xem `k8s/advanced/postgres.yaml`
   (mục 9) để thực hành StatefulSet + PersistentVolumeClaim, rồi đổi `DATABASE_URL` trong
   `configmap.yaml`.
2. **HorizontalPodAutoscaler (HPA)** — hiện `replicas: 2` là số cố định; HPA tự tăng/giảm theo tải
   thật. Cần cài `metrics-server` trước (xem mục 9.2).
3. **Ingress thay vì port-forward** — port-forward chỉ dùng để debug tạm; Ingress mới là cách expose
   service ra ngoài đúng chuẩn production-like.
4. **(Đã làm một phần)** Image đã gỡ `torch`/`torchvision`/`langchain*` (không gì import)
   và dùng `opencv-python-headless` thay vì `opencv-python` (slim thiếu `libGL`). Nếu muốn nhẹ hơn
   nữa: tách requirements hoặc multi-stage build để loại build-tools khỏi image cuối.
5. **(Đã làm)** `/health` giờ trả thêm field `db` (check `SELECT 1` thật) — readinessProbe đã phản
   ánh đúng trạng thái DB. Khi DB down, `db` sẽ là `"error: ..."` (status vẫn 200 để dễ debug;
   nếu muốn pod bị rút traffic thì đổi sang 503 khi `db` lỗi).
6. **Secret quản lý bằng công cụ chuyên dụng** — `secret.yaml` hiện chỉ minh hoạ; thực tế nên dùng
   **Sealed Secrets** hoặc **External Secrets Operator** (đọc từ Vault/AWS Secrets Manager) để không
   bao giờ có secret plaintext trong git.
7. **Helm chart hoá** — khi số file YAML nhiều lên (namespace, hpa, ingress, postgres...), nên gói
   thành 1 Helm chart để `helm install`/`helm upgrade` thay vì `kubectl apply -f` nhiều file rời rạc,
   và dễ tham số hoá (`values.yaml`) giữa các môi trường dev/staging/prod.
8. **NetworkPolicy mặc định "deny-all"** rồi mở dần từng luồng cần thiết (hiện tại mọi pod gọi được
   mọi pod — xem mục 9.5).
9. **PodDisruptionBudget** — đảm bảo khi node bị bảo trì (`kubectl drain`), luôn còn ít nhất 1 pod
   `py-app` sống, tránh downtime toàn bộ.
10. **CI build & push image lên registry thật** (Docker Hub/GHCR) thay vì `kind load` thủ công — bước
    tự nhiên tiếp theo khi rời môi trường học tập.

---

## 9. Các file YAML nâng cao để học sâu hơn

Nằm ở `k8s/advanced/` — **không** nằm chung với `k8s/` cơ bản, để bạn chủ động áp dụng từng cái một
khi đã hiểu, tránh phá cluster đang chạy ổn.

### 9.1. `advanced/namespace.yaml` — cô lập tài nguyên
```bash
kubectl apply -f k8s/advanced/namespace.yaml
kubectl apply -f k8s/ -n py-practice   # áp lại bộ cơ bản vào namespace riêng
kubectl get pods -n py-practice
```
Học được: mọi resource K8s (trừ vài loại cluster-scoped như Node, PersistentVolume) đều thuộc 1
namespace; namespace là cách chia "khu vực" logic trong cùng 1 cluster — ví dụ tách `dev`/`staging`,
hoặc tách theo team, mà không cần nhiều cluster vật lý.

### 9.2. `advanced/hpa.yaml` — auto-scale theo tải CPU thật
Cần cài `metrics-server` trước (bản thường không tương thích thẳng với `kind`, cần patch
`--kubelet-insecure-tls`):
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

kubectl apply -f k8s/advanced/hpa.yaml
kubectl get hpa -w
```
Để tạo tải test (app không có endpoint nặng CPU sẵn), chạy 1 pod tạm gọi `/health` liên tục:
```bash
kubectl run load-generator --image=busybox --restart=Never -- /bin/sh -c \
  "while true; do wget -q -O- http://py-app:8888/health; done"
```
Học được: khác biệt `requests` (baseline để tính %) vs `limits`; HPA đọc metric qua
`metrics-server`, không phải qua Prometheus (đó là bài toán khác — custom metrics).

### 9.3. `advanced/ingress.yaml` — expose ra ngoài đúng chuẩn
Cần cài Ingress Controller trước (ingress-nginx, tương thích tốt với `kind`):
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s

kubectl apply -f k8s/advanced/ingress.yaml
echo "127.0.0.1 py-app.local" | sudo tee -a /etc/hosts
curl http://py-app.local/health
```
Học được: khác biệt Service (Layer 4, chỉ cân bằng tải TCP/UDP) vs Ingress (Layer 7, route theo
host/path HTTP, có thể gắn TLS termination ở đây).

### 9.4. `advanced/postgres.yaml` — StatefulSet + PersistentVolumeClaim
```bash
kubectl apply -f k8s/advanced/postgres.yaml
kubectl get pods -w        # đợi postgres-0 Running
kubectl get pvc            # thấy PersistentVolumeClaim tự động bound với 1 PersistentVolume
```
Sau đó sửa `k8s/configmap.yaml`:
```yaml
DATABASE_URL: "postgresql://py_app:py_app_password@postgres:5432/py_app"
```
rồi `kubectl apply -f k8s/configmap.yaml && kubectl rollout restart deployment py-app`.

Học được: khác biệt Deployment (pod đồng nhất, thay thế lẫn nhau tự do, không cần identity ổn định)
vs StatefulSet (pod có tên ổn định `postgres-0`, `postgres-1`..., mỗi pod gắn **1 volume riêng**
không dùng chung — bắt buộc cho database, không thể dùng Deployment thường cho Postgres nhiều
replica).

### 9.5. `advanced/networkpolicy.yaml` — giới hạn traffic giữa pod
`kind` mặc định dùng CNI `kindnet`, **không** áp dụng NetworkPolicy — cần tạo cluster mới với Calico:
```bash
kind create cluster --name py-practice-netpol --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true
EOF
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/calico.yaml
kubectl apply -f k8s/advanced/networkpolicy.yaml
```
Học được: mặc định K8s network là "allow-all" giữa mọi pod trong cluster — NetworkPolicy giống
firewall rule ở tầng pod, áp dụng least-privilege (chỉ pod `py-app` được gọi vào `postgres:5432`).

### 9.6. `advanced/cronjob.yaml` — tác vụ định kỳ
```bash
kubectl apply -f k8s/advanced/cronjob.yaml
kubectl get cronjob
kubectl get jobs -w        # mỗi phút thấy 1 Job mới được CronJob tạo ra
kubectl logs job/<tên-job-cụ-thể>
```
Học được: khác biệt Job (chạy tới khi xong thì dừng, không tự lặp) vs CronJob (tạo Job mới theo lịch
cron) vs Deployment (chạy mãi, tự restart nếu chết) — 3 mô hình vòng đời khác nhau cho 3 loại workload
khác nhau.

---

## 10. Troubleshooting thường gặp

| Triệu chứng | Nguyên nhân hay gặp | Cách kiểm tra/sửa |
|---|---|---|
| Pod ở trạng thái `ImagePullBackOff`/`ErrImageNeverPull` | Quên `kind load docker-image` sau khi build lại image | `kind load docker-image py-app:local --name py-practice` |
| Pod `CrashLoopBackOff` | App lỗi lúc khởi động | `kubectl logs <pod>` (log lần chạy trước: thêm `--previous`) |
| Pod kẹt ở `Pending` mãi | Không đủ CPU/RAM theo `resources.requests`, hoặc chưa có node | `kubectl describe pod <pod>` xem mục `Events` |
| `curl localhost:8888` không phản hồi | Quên chạy `kubectl port-forward`, hoặc chạy sai `svc/py-app` | Kiểm tra `kubectl get svc`, `kubectl get endpoints py-app` (phải có IP pod, không rỗng) |
| Sửa code nhưng chạy vẫn ra bản cũ | Quên build lại image, hoặc quên `kubectl rollout restart` | Build → `kind load` → `rollout restart` — thiếu 1 bước là dính bản cũ |
| `kubectl` báo "context không tồn tại" | Chưa `kind create cluster` hoặc dùng sai `--name` | `kubectl config get-contexts`, `kind get clusters` |
