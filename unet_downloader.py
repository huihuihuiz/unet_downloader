import os
import requests
import folder_paths
from server import PromptServer
from aiohttp import web
import urllib.parse

# ---------------------------------------
# Secure path join helper
# ---------------------------------------
def safe_join(base_dir, user_path):
    base = os.path.abspath(base_dir)
    final_path = os.path.abspath(os.path.join(base, user_path))

    # Ensure path is strictly inside base directory
    if os.path.commonpath([base, final_path]) != base:
        raise ValueError("Illegal path")

    return final_path


class UNetDownloader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "unet_name": ("STRING", {"default": "flux1-dev-fp8.safetensors"}),
                "download_url": ("STRING", {"default": "https://example.com/unet.safetensors"}),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "download_unet"
    OUTPUT_NODE = True
    CATEGORY = "utils"

    def download_unet(self, unet_name, download_url):
        # Real download handled via HTTP endpoint
        return ()


# ---------------------------------------
# Download UNet from URL -> save to server
# ---------------------------------------
@PromptServer.instance.routes.post("/unet_downloader/download")
async def download_unet_endpoint(request):
    try:
        data = await request.json()

        unet_name = data.get("unet_name", "").strip()
        download_url = data.get("download_url", "").strip()

        if not unet_name or not download_url:
            return web.json_response(
                {"error": "Missing unet_name or download_url"}, status=400
            )

        unet_directory = folder_paths.get_folder_paths("unet")[0]

        try:
            file_path = safe_join(unet_directory, unet_name)
        except ValueError:
            return web.json_response({"error": "Illegal file path"}, status=403)

        # Create subfolders if needed
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if os.path.exists(file_path):
            return web.json_response(
                {"message": f"File {unet_name} already exists"}, status=200
            )

        # Download file
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return web.json_response(
            {"message": f"Successfully downloaded {unet_name}"}, status=200
        )

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ---------------------------------------
# List all existing UNet files
# ---------------------------------------
@PromptServer.instance.routes.get("/unet_downloader/list")
async def list_unets_endpoint(request):
    try:
        unet_directory = folder_paths.get_folder_paths("unet")[0]
        unet_files = []

        if os.path.exists(unet_directory):
            for root, dirs, files in os.walk(unet_directory):
                for file in files:
                    if file.endswith((".safetensors", ".ckpt", ".pt", ".pth")):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, unet_directory)
                        unet_files.append(
                            {
                                "name": relative_path,
                                "size": os.path.getsize(file_path),
                            }
                        )

        return web.json_response({"unets": unet_files}, status=200)

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ---------------------------------------
# Web UI (HTML embedded)
# ---------------------------------------
@PromptServer.instance.routes.get("/unet_downloader")
async def serve_unet_downloader_page(request):
    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>ComfyUI UNet 模型下载器</title>
<style>
body{font-family:Arial, sans-serif;max-width:1000px;margin:0 auto;background:#f5f5f5;padding:20px;}
.container{background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1);}
h1{text-align:center;color:#333;}
input,button{padding:10px;margin-top:5px;width:100%;}
button{cursor:pointer;}
.unet-item{border-bottom:1px solid #eee;padding:6px 0;display:flex;justify-content:space-between;align-items:center;}
.download-btn{margin-left:10px;width:auto;background-color:#0275d8;color:white;border:none;border-radius:4px;padding:8px 12px;}
.download-btn:hover{background-color:#0260d0;}
.info-box{background-color:#e7f3ff;border-left:4px solid #2196F3;padding:15px;margin-bottom:20px;border-radius:4px;}
.info-box h3{margin-top:0;color:#1976D2;}
.info-box ul{margin:10px 0;padding-left:20px;}
.warning{background-color:#fff3cd;border-left:4px solid #ffc107;padding:10px 15px;margin-bottom:15px;border-radius:4px;color:#856404;}
.button-group{margin-bottom:15px;}
.button-group button{width:auto;display:inline-block;margin-right:10px;}
.refresh-btn{background-color:#5bc0de;color:white;border:none;border-radius:4px;}
.refresh-btn:hover{background-color:#31b0d5;}
.download-all-btn{background-color:#f0ad4e;color:white;border:none;border-radius:4px;}
.download-all-btn:hover{background-color:#ec971f;}
.submit-btn{background-color:#4CAF50;color:white;border:none;border-radius:4px;}
.submit-btn:hover{background-color:#45a049;}
.result{margin-top:20px;padding:15px;border-radius:4px;display:none;}
.success{background-color:#dff0d8;color:#3c763d;border:1px solid #d6e9c6;}
.error{background-color:#f2dede;color:#a94442;border:1px solid #ebccd1;}
.progress{margin-top:10px;font-size:14px;color:#666;}
</style>
</head>
<body>
<div class="container">
<h1>ComfyUI UNet 模型下载器</h1>

<div class="info-box">
<h3>📦 常用 FLUX UNet 模型</h3>
<ul>
<li><strong>flux1-dev-fp8.safetensors</strong> - FLUX.1 Dev FP8 量化版本 (~24GB)</li>
<li><strong>flux1-dev-kontext_fp8_scaled.safetensors</strong> - FLUX.1 Dev Kontext FP8 (~24GB)</li>
<li><strong>flux1-schnell-fp8.safetensors</strong> - FLUX.1 Schnell FP8 快速版本 (~24GB)</li>
</ul>
</div>

<div class="warning">
⚠️ 注意：UNet 模型文件通常非常大 (20GB-50GB)，下载需要较长时间和充足的磁盘空间。
</div>

<form id="downloadForm">
<input id="unetName" placeholder="例如: flux1-dev-fp8.safetensors" required>
<input id="downloadUrl" type="url" placeholder="https://example.com/unet.safetensors" required>
<button type="submit" class="submit-btn">下载 UNet 模型</button>
</form>

<div id="result" class="result"></div>

<h3>已有 UNet 模型</h3>
<div class="button-group">
<button id="refreshBtn" class="refresh-btn">刷新列表</button>
<button id="downloadAllBtn" class="download-all-btn">全部下载到本地</button>
</div>
<div id="unetList"></div>
<div id="progress" class="progress"></div>
</div>

<script>
const baseUrl = window.location.origin;
let allUnets=[];

async function loadUNetList(){
    const r=await fetch(`${baseUrl}/unet_downloader/list`);
    const d=await r.json();
    let html='';
    allUnets=d.unets||[];
    allUnets.forEach(u=>{
        const gb=(u.size/1024/1024/1024).toFixed(2);
        html+=`<div class="unet-item"><span>${u.name} (${gb}GB)</span>
        <button class="download-btn" onclick="downloadUNet('${encodeURIComponent(u.name)}')">下载</button></div>`;
    });
    document.getElementById('unetList').innerHTML=html||'暂无文件';
}

function downloadUNet(name){
    const link=document.createElement('a');
    link.href=`${baseUrl}/unet_downloader/download_file/${name}`;
    link.download=name.split('/').pop();
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

document.getElementById('downloadForm').addEventListener('submit',async e=>{
    e.preventDefault();
    const resultDiv=document.getElementById('result');
    resultDiv.className='result success';
    resultDiv.textContent='开始下载，请稍候...';
    resultDiv.style.display='block';
    const data={
        unet_name:unetName.value,
        download_url:downloadUrl.value
    };
    const r=await fetch(`${baseUrl}/unet_downloader/download`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(data)
    });
    const d=await r.json();
    resultDiv.className=r.ok?'result success':'result error';
    resultDiv.textContent=d.message||d.error;
    if(r.ok){document.getElementById('downloadForm').reset();loadUNetList();}
});

document.getElementById('refreshBtn').onclick=loadUNetList;

document.getElementById('downloadAllBtn').onclick=async ()=>{
    const progressDiv=document.getElementById('progress');
    for(let i=0;i<allUnets.length;i++){
        progressDiv.textContent=`正在下载 ${i+1}/${allUnets.length}: ${allUnets[i].name}`;
        downloadUNet(encodeURIComponent(allUnets[i].name));
        await new Promise(r=>setTimeout(r,500));
    }
    progressDiv.textContent=`完成！已下载 ${allUnets.length} 个文件`;
    setTimeout(()=>{progressDiv.textContent='';},3000);
}

window.onload=loadUNetList;
</script>
</body>
</html>
"""
    return web.Response(text=html_content, content_type="text/html")


# ---------------------------------------
# Download existing UNet -> send to user
# ---------------------------------------
@PromptServer.instance.routes.get("/unet_downloader/download_file/{filename:.+}")
async def download_unet_file(request):
    try:
        filename = urllib.parse.unquote(request.match_info["filename"])
        unet_directory = folder_paths.get_folder_paths("unet")[0]

        try:
            file_path = safe_join(unet_directory, filename)
        except ValueError:
            return web.json_response({"error": "Forbidden"}, status=403)

        if not os.path.exists(file_path):
            return web.json_response({"error": "File not found"}, status=404)

        return web.FileResponse(
            file_path,
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(file_path)}"'
            },
        )

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ---------------------------------------
# Node mappings
# ---------------------------------------
NODE_CLASS_MAPPINGS = {
    "UNetDownloader": UNetDownloader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UNetDownloader": "UNet Downloader"
}
