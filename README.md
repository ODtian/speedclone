# Usage/使用方法
#### 项目目录：
```
├─ speedclone
│  ├─ bar
│  │  ├─ __init__.py
│  │  ├─ basebar.py
│  │  ├─ commonbar.py
│  │  └─ slimbar.py
│  ├─ transfers
│  │  ├─ __init__.py
│  │  ├─ filesystem.py
│  │  ├─ googledrive.py
│  │  ├─ onedrive.py
│  │  └─ onedriveshared.py
│  ├─ __init__.py
│  ├─ args.py
│  ├─ error.py
│  ├─ manager.py
│  └─ utils.py
├─ .gitattributes
├─ .gitignore
├─ README.md
├─ main.py
├─ requirements.txt
└─ speedclone.json
```
#### 基本命令：
```
python main.py [source_config_name]:/path/to/your/file/or/dir [dest_config_name]:/path/to/your/dest/dir
```
以上命令将把文件夹或文件`/path/to/your/file/or/dir`传输到远程目录`/path/to/your/dest/dir`。

注：当`/path/to/your/file/or/dir`为文件夹时，这个文件夹会成为远程目录的子文件夹。

#### 选项：
```
usage: main.py [-h] [-I INTERVAL] [--client-sleep CLIENT_SLEEP] [-W WORKERS]
               [-C CHUNK_SIZE] [-S STEP_SIZE] [-B BAR] [--conf CONF]

optional arguments:
  -h, --help            show this help message and exit
  -I INTERVAL, --interval INTERVAL
                        Interval time when putting workers into thread pool
  -W WORKERS, --workers WORKERS
                        The number of workers
  -C CHUNK_SIZE, --chunk-size CHUNK_SIZE
                        Size of single request in multiple chunk uploading
  -S STEP_SIZE, --step-size STEP_SIZE
                        Size of chunk when updating the progress bar
  -B BAR, --bar BAR     Name of the progress bar
  --client-sleep CLIENT_SLEEP
                        Time to sleep when client has been throttled
  --conf CONF           Path to the config file
```
其中`--bar`选项目前可选项有`common`和`slim`，指的是进度条的样式，默认为`common`。
###### slim样式：
```
100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████▉| 92.5G/92.6G [3:31:39<00:00, 7.82MB/s
100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████▋| 94060/94227 [3:31:39<00:22,  7.41tasks/s]
```
上方的进度条是文件总大小和上传进度/速度，下方的是文件的总个数和完成的进度/速度。

注：此文件总大小和文件总数会随着上传任务添加进线程池而产生变化，并不代表总数。完成传输后的大小和总数并不一定，错误重试的也会被记入，因此正常情况是多于的。
###### common样式：
```
| 图\j653b9c5.bmp       | 100.00% |████████████████████|   191k / 191k   [9.32MB/s 00:00>00:00]
| 图\k9wabztp.bmp       | 100.00% |████████████████████|   191k / 191k   [7.53MB/s 00:00>00:00]
| 图\l1nqc8yx.bmp       | 100.00% |████████████████████|   186k / 186k   [7.33MB/s 00:00>00:00]
| 图\l64s24x8.bmp       | 100.00% |████████████████████|  1.83M / 1.83M  [66.1MB/s 00:00>00:00]
| 图\librejp.gif        | 100.00% |████████████████████|  73.3k / 73.3k  [2.68MB/s 00:00>00:00]
| 图\MATRIX_130916_WWW_ | 100.00% |████████████████████|   410k / 410k   [15.5MB/s 00:00>00:00]
| 图\MATRIX_131357_HOS_ | 100.00% |████████████████████|   927k / 927k   [33.9MB/s 00:00>00:00]
| 图\MATRIX_131440_IQQ_ | 100.00% |████████████████████|   938k / 938k   [34.3MB/s 00:00>00:00]
| 图\MATRIX_133735_YKF_ | 100.00% |████████████████████|   459k / 459k   [16.2MB/s 00:00>00:00]
```
#### 配置文件：
###### 指定配置文件：
默认的配置文件是`./speedclone.json`,可以在选项中指定路径。
###### 配置文件概览：
```json
{
  "transfers": {
  	///
  },
  "bar": {
  	///
  },
  "configs": {
  	"config_name":{
  	/// config1
  	},
  	"config_name":{
  	/// config2
  	}
}
```
将配置放到`"configs"`中，就可以在命令中使用了。
###### Google Drive：
```json
{
	"service_account": false,  // 是否使用sa（service account），必选。
	"token_path": "/path/to/token_file.json",  // 你的凭证文件，如果 service_account 为是，则指定为下载下来的凭证文件路径，或文件夹；
												  若否，则将验证后的json信息（详见下方）保存为文件，并指定为文件路径或文件夹。
	"transfer": "gd",  // 传输方式，此处为gd
	"client": {        // oauth2凭证信息，如果 service_account 为是则不需要。
	  "client_id": "client_id here",
	  "client_secret": "client_secret here"
	},
	"proxies": {      // 代理，支持所有requests支持的代理方式
	  "http": "",
	  "https": ""
	},
	"root": "root",   // 根目录，为文件夹ID，root代表个人盘的根目录，可以为个人盘内的文件夹；
						 如果使用Team Drive，则为Team Drive的ID或盘内文件夹的ID。
	"drive_id": ""    //盘ID，如果是个人盘无需指定，Team Drive需要指定为盘ID。
}
```
个人账户json信息 (rclone配置文件的token)：
```
{
  "access_token": "your token",
  "expires_in": 3599,
  "refresh_token": "your token",
  "scope": "https://www.googleapis.com/auth/drive",
  "token_type": "Bearer"
}
```
###### OneDrive：
```
{
	"token_path": "/path/to/accounts/dir",  // 你的凭证文件，token文件或文件夹路径，如果用过api应该知道是啥。
	"transfer": "od",
	"drive_id": "your drive id",  // drive id，知道用过api的应该也知道，可以通过指定此值上传到共享库或者sharepoint文档库。
	"client": {  // oauth2凭证信息，client secret可以不指定，取决于你的应用程序是否是私有的，可以看文档解释的很清楚 -> https://developer.microsoft.com/zh-cn/graph
	  "client_id": "your client id",
	  "client_secret": "your client secret  # if your app is not private, then fill nothing"
	}
}
```
###### OneDrive分享链接：
```
{
	"is_folder": true,  // 分享链接是否是单目录形式的，打开只有一个文件的话就不是。
	"transfer": "odshare"
}
```
注：这个暂时还没写，不过只是暂时没整合进这个项目，所以应该速度很快。
###### 文件系统：
```
{
	"transfer": "fs"
}
```
