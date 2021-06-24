
<h1 align="center">
    zoomrec	
</h1>

<h4 align="center">
	A all-in-one solution to automatically join and record Zoom meetings.
</h4>


<p align="center">
  <img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/kastldratza/zoomrec">
  <img alt="GitHub issues" src="https://img.shields.io/github/issues/kastldratza/zoomrec">
	<img alt="GitHub Workflow Status" src="https://img.shields.io/github/workflow/status/kastldratza/zoomrec/CodeQL?label=CodeQL">
  <img alt="GitHub Workflow Status" src="https://img.shields.io/github/workflow/status/kastldratza/zoomrec/Publish%20Docker%20image?label=Docker">
  <img alt="GitHub Workflow Status" src="https://img.shields.io/github/workflow/status/kastldratza/zoomrec/Snyk?label=Snyk">
  <img alt="GitHub Workflow Status" src="https://img.shields.io/github/workflow/status/kastldratza/zoomrec/Snyk%20Container?label=Snyk%20Container">
</p>

---

- **Python3** - _Script to automatically join Zoom meetings and control FFmpeg_
- **FFmpeg** - _Triggered by python script to start/stop screen recording_
- **Docker** - _Headless VNC Container based on Ubuntu 20.04 with Xfce window manager and TigerVNC_

---

![Join a test meeting](doc/join-meeting.gif)

---

## Installation

The entire mechanism runs in a Docker container. So all you need to do is install Docker and use the image from Docker Hub.

### Requirements

- Docker - [https://docs.docker.com/get-docker/]()

### Docker Registry

Docker images are build and pushed automatically to **Docker Hub** and **GitHub** Registry.

So you can choose and use one of them:
- ```ghcr.io/kastldratza/zoomrec:master```
- ```kastldratza/zoomrec:latest```

*For my examples in this README I used* ```kastldratza/zoomrec:latest```

---

## Usage

- Container saves recordings inside container at **/home/zoomrec/recordings**
- The current directory is used to mount recordings-Folder, but can be changed if needed
  - Please check use of paths on different operating systems
  - Please check permissions for used directory
- Container stops when Python script is terminated
- Zoomrec uses a CSV file with entries of Zoom meetings to record them
  - The csv can be passed as seen below (mount as volume or add to docker image)

### CSV structure
CSV must be fromatted as in example/meetings.csv
  - Delimiter must be a semicolon "**;**"
  - Only meetings with flag "**record = true**" are joined and recorded
  - "**description**" is used for filename when recording
  - "**duration**" in minutes (+5 minutes to the end)

weekday | time | duration | id | password | description | record
-------- | -------- | -------- | -------- | -------- | -------- | --------
monday | 09:55 | 60 | 111111111111 | 741699 | Important_Meeting | true
monday | 14:00 | 90 | 222222222222 | 321523 | Unimportant_Meeting | false

### VNC
You can connect to zoomrec via vnc and see what is happening.
#### Connect (default)
Hostname | Port | Password
-------- | -------- | --------
localhost   | 5901   | zoomrec

### Preparation
To have access to the recordings, a volume is mounted, so you need to create a folder that container users can access.

**[ IMPORTANT ]**
#### Create folder for recordings and set permissions (on Host)
```
mkdir -p recordings
chown -R 1000:1000 recordings
```

### Flags
#### Set timezone (default: Europe/Berlin)
```
docker run -d --restart unless-stopped \
  -e TZ=Europe/Berlin \
  -v $(pwd)/recordings:/home/zoomrec/recordings \
  -v $(pwd)/example/meetings.csv:/home/zoomrec/meetings.csv:ro \
  -p 5901:5901 \
kastldratza/zoomrec:latest
```
#### Set debugging flag
   - screenshot on error
   - record joining
   - do not exit container on error
```
docker run -d --restart unless-stopped \
  -e DEBUG=True \
  -v $(pwd)/recordings:/home/zoomrec/recordings \
  -v $(pwd)/example/meetings.csv:/home/zoomrec/meetings.csv:ro \
  -p 5901:5901 \
kastldratza/zoomrec:latest
```


### Windows / _cmd_

```cmd
docker run -d --restart unless-stopped \
  -v %cd%\recordings:/home/zoomrec/recordings \
  -v %cd%\example\meetings.csv:/home/zoomrec/meetings.csv:ro \
  -p 5901:5901 \
kastldratza/zoomrec:latest
```

### Windows / _PowerShell_

```powershell
docker run -d --restart unless-stopped \
  -v ${PWD}/recordings:/home/zoomrec/recordings \
  -v ${PWD}/example/meetings.csv:/home/zoomrec/meetings.csv:ro \
  -p 5901:5901 \
kastldratza/zoomrec:latest
```

### Linux / macOS

```bash
docker run -d --restart unless-stopped \
  -v $(pwd)/recordings:/home/zoomrec/recordings \
  -v $(pwd)/example/meetings.csv:/home/zoomrec/meetings.csv:ro \
  -p 5901:5901 \
kastldratza/zoomrec:latest
```

## Customization example

### Add meetings.csv to image

```bash
# Switch to example directory
cd example

# Build new image by customized Dockerfile
docker build -t kastldratza/zoomrec-custom:latest .

# Run image without mounting meetings.csv
# Linux
docker run -d --restart unless-stopped -v $(pwd)/recordings:/home/zoomrec/recordings -p 5901:5901 kastldratza/zoomrec-custom:latest

# Windows / PowerShell
docker run -d --restart unless-stopped -v ${PWD}/recordings:/home/zoomrec/recordings -p 5901:5901 kastldratza/zoomrec-custom:latest

# Windows / cmd
docker run -d --restart unless-stopped -v %cd%\recordings:/home/zoomrec/recordings -p 5901:5901 kastldratza/zoomrec-custom:latest
```

## Supported actions

- [x] Show when the next meeting starts
- [x] _Join a Meeting_ from csv
  - [x] with id and password
  - [ ] with url
- [x] Wrong error: _Invalid meeting ID_ | **Leave**
- [x] _Join with Computer Audio_
- [x] _Please wait for the host to start this meeting._
- [x] _Please wait, the meeting host will let you in soon._
- [x] _Enter Full Screen_
- [x] Switch to _Speaker View_
- [x] Continuously check: _This meeting is being recorded_ | **Continue**
- [x] Continuously check: _Hide Video Panel_
- [x] Continuously check: _This meeting has been ended by host_
- [x] Quit ffmpeg gracefully on abort
- [ ] _Host is sharing poll results_
- [ ] _This meeting is for authorized attendees only_
  - [x] Leave meeting
  - [ ] _Sign In to Join_
- [ ] Breakout Rooms
- [ ] ...

## Testing

Create unittests for different use cases:
- [ ] Join meeting
- [ ] Start / Stop ffmpeg and check if file was created
- [ ] ...

### Tested with
- [x] Zoom 5.6.4
- [x] Ubuntu 20.04
  - [x] Desktop
  - [x] Server
- [ ] Windows 10

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
