# patreon-email-dl
An IMAP based Patreon download Docker container
# Under the hood:
  * yt-dlp to download embedded links
  * ffmpeg to change metadata title
  *  [jlesage/docker-firefox](https://github.com/jlesage/docker-firefox) to easily grab cookie files. (not necassary)
# How to use:

## 1. CREATE A NEW GMAIL account and generate an app password for your Gmail account.
**NOTE:** I personally created a new email, and am forwarding emails from my Patreon account's email to the new account. I **highly recommend** this because you can filter the emails prior to processing them. [Read about Gmail forwarding here](https://support.google.com/mail/answer/10957?hl=en)

### From https://support.google.com/mail/answer/185833?hl=en:
---
**Create & use app passwords**

**Important**: To create an app password, you need 2-Step Verification on your Google Account.

If you use 2-Step-Verification and get a "password incorrect" error when you sign in, you can try to use an app password.

[Create and manage your app passwords](https://myaccount.google.com/apppasswords). You may need to sign in to your Google Account.

If you’ve set up 2-Step Verification but can’t find the option to add an app password, it might be because:
* Your Google Account has 2-Step Verification [set up only for security keys](https://support.google.com/accounts/answer/6103523).
* You’re logged into a work, school, or another organization account.
* Your Google Account has [Advanced Protection](https://support.google.com/accounts/answer/7539956).
---

## 2. Create and populate the appropriate fields in the .env file

### See an example .env file [here](.env.example)

Fields:
| Variable | Value |
| --- | --- |
| SUBJECT_KEYWORDS: | A list of keywords found in the email subject. This is used to sepecify which videos to download. |
| OUTPUT_FOLDER: | The host's real folder used in the Docker-Compose file. *Example: //nas.local/plex/media/Patreon/* |
| CRON_SCHEDULE: | Cron based schedule formating. *You can use this site to build the schedule: https://crontab.guru/* |
| AUTO_MAKE_FOLDERS: | Auto create subfolders based on the sender name. Email auto-forwarding maintains the senders name, so this should be accurate to the Patreon account's name, since that is how the notification emails arrive. |

## 3. Create and populate the appropriate fields in the patreon_email_dl.secret file

### See an example patreon_email_dl.secret file [here](patreon_email_dl.secret.example)

Fields:
| Variable | Value |
| --- | --- |
| EMAIL: | The account's email that will be scanned via IMAP |
| APP_PASSWORD: | The app password form step 1. |
| SENDER_FILTER: | The sender of the email. This is generally "bingo@patreon.com" |

## 4. Create/populate your docker-compose file

## 5. Run `sudo docker-compose up -d firefox_patreon_email_dl` to build and run the Firefox container.

## 6. Visit https://(DOCKER_HOST):5801 (<- default) and sign into Patreon.

*There is a nice tab on the left side of the screen for clipboard operations.* the cookies have now been generated, and you can stop this container. You will have to log in again when the cookies expire (about a year). 

## 7. You can now run `sudo docker-compose up -d patreon_email_dl` to start the script.

# Todo
* Fix logging
* Add Plex scan media support, maybe
