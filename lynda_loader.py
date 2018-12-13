import requests
import re
from bs4 import BeautifulSoup
import os
from sys import stdout


def find_lynda_video(html, courseID):
    soup = BeautifulSoup(html, "lxml")      # "lxml" OS-specific, best for Windows
    data_conviva = eval(soup.find("video").get("data-conviva"))     # evaluate string to dict
    course_id = data_conviva["CourseId"]
    if int(course_id) == int(courseID):
        video_url = soup.find("video").get("data-src")
        name = name_the_video(video_url, data_conviva)
        return video_url, name
    else:
        return None


def name_the_video(video_url, data_conviva):
    index = re.findall(r"SD/\S+.mp4", video_url)
    index = str(index).split("_")[1] + "_" + str(index).split("_")[2]
    name = str(data_conviva["VideoTitle"])
    return index + " - " + name


def get_playlist_urls(html, course_url):
    splitted = str(course_url).split("/")
    url = re.findall(r"(href=\"https://www.lynda.com/" + splitted[3] + r"/\S+\")", html)
    urls = []
    for i in url:
        urls.append(str(i).split("\"")[1])
    print("Found Playlist-URLs: " + str(len(set(urls))))
    return set(urls)


def find_token(html):       # find -_- for formdata
    token = re.findall(r"name=\"-_-\" value=\"\S+==\"", html)
    token = token[0].split(" ")[1]
    token = token.split("\"")[1]
    print("Found token \"-_-\":", token)
    return str(token)


def find_lynda_login_status(txt):
    status = re.findall(r"LyndaLoginStatus=\S+;", txt)
    return status


def get_course_title_and_create_folder(html, download_path, course_id):
    soup = BeautifulSoup(html, "lxml")      # "lxml" OS-specific, best for Windows
    course_title = soup.find(id="embed-share-url").get("data-course-title")
    course_title = str(course_title).replace(":", " -")
    course_title = "".join(e for e in course_title if (e.isalnum() or e in (" ", "_", "-", ",", ".")))
    folder_name = "Course " + str(course_id) + " - " + str(course_title)
    directory = download_path + folder_name
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory + "\\"


def main():
    # login to Lynda.com
    session_requests = requests.Session()

    login_url = "https://www.lynda.com/signin"
    first_request_url = "https://www.lynda.com/signin/password"
    second_request_url = "https://www.lynda.com/signin/user"
    course_url = input("Put in the URL of the Course you want to download: ")

    result = session_requests.get(login_url, headers=dict(referer="https://www.lynda.com/"))
    token = find_token(result.text)

    email = input("Put in your Lynda.com-Username (E-Mail): ")
    password = input("Put in your Lynda.com-Password: ")

    home = os.path.expanduser("~")
    download_dir = home + ("/Downloads/" if os.name == "posix" else "\\Downloads\\")
    download_path = download_dir + "Lynda-Downloads\\"

    print("POST token + E-Mail to " + login_url + "...")
    FirstPayload = {
        "-_-": token,
        "email": email,
    }
    result = session_requests.post(
        login_url,
        data=FirstPayload,
        headers=dict(referer=login_url)
    )
    token = find_token(result.text)
    print("POST (email): Request Successful: ", result.ok, " --- Status-Code: ", result.status_code)

    print("POST token + E-Mail + password to " + second_request_url + "...")
    SecondPayload = {
        "-_-": token,
        "email": email,
        "password": password,
        "remember": "on"
    }

    result = session_requests.post(
        second_request_url,
        data=SecondPayload,
        headers=dict(referer=first_request_url)
    )
    print("POST (password): Request Successful: ", result.ok, " --- Status-Code: ", result.status_code)

    # open course frontpage and find course-ID for checking of not downloading other courses' videos

    result_new = session_requests.get(course_url, headers=dict(referer=course_url))
    html = result_new.text
    courseID = str(re.findall(r"data-course-id=\"\S+\"", html)).split("\"")[1]
    print("Course-ID: ", courseID)

    download_path = get_course_title_and_create_folder(result_new.text, download_path, courseID)

    # parse course frontpage for all the contained playlist-items
    playlistURLs = get_playlist_urls(html, course_url)

    # parse all the playlist-sites for video-urls
    # TODO: move this to separate function
    print("Parsing Playlist...")
    video_urls = [find_lynda_video(html, courseID)]
    index = 0
    url_count = len(playlistURLs)
    for curURL in playlistURLs:
        index += 1
        text = "\r> Parsing (" + str(index) + "/" + str(url_count) + ") : " + str(curURL)
        stdout.write(text)
        stdout.flush()
        result_new = session_requests.get(curURL, headers=dict(referer=curURL))
        html = result_new.text
        video_urls.append(find_lynda_video(html, courseID))
    print("\n")
    print(">>> Done")

    # download video
    for video in video_urls:
        if video is not None:
            # set filename and check if the file already exists
            video_name = video[1]
            video_name = "".join(e for e in video_name if (e.isalnum() or e in (" ", "_", "-")))        # remove special characters
            filename = download_path + courseID + " - " + video_name + ".mp4"
            if os.path.isfile(filename):
                print("File " + filename + " already exists!")
                # TODO: replace existing file dialogue?
                continue

            # requesting URL-data and getting filesize from header (for progress-indicator)
            if video[0] != "":
                print("Downloading URL: " + video[0])
                video_result = session_requests.get(video[0], headers=dict(referer=video[0]), stream=True)
                video_size = int(video_result.headers.get("Content-Length"))
                print("Downloading " + video_name + " (Bytes: " + str(video_size) + ") ...")
                video_file = open(filename, "wb")
                counter = 0

                # writing file-chunks to defined file and indicate progress by percentage and progressbar
                for chunk in video_result.iter_content(chunk_size=1024):
                    if chunk:       # filter out keep-alive new chunks
                        video_file.write(chunk)
                    counter += 1
                    loaded = counter * 1024
                    progress_percent = (loaded/video_size) * 100
                    progress_bar = " [" + "="*(int(progress_percent)//2) + " "*(50-(int(progress_percent)//2)) + "] "
                    text = ""
                    if loaded <= video_size:
                        text = "\r" + str(loaded) + "/" + str(video_size) + progress_bar + "({0:.2f}%)".format(progress_percent)
                    else:
                        text = "\r> " + str(video_size) + "/" + str(video_size) + progress_bar + "(100.00%)" + " DONE"
                    stdout.write(text)
                    stdout.flush()
                video_file.close()
                print(" >>> Finished downloading " + video_name)
        else:
            continue
    print("FINISHED!")


if __name__ == '__main__':
    main()
