# Bibliographic Record AI Prompt Generator


## Usage:

1. open the terminal in a permanent location where it will live. (If it moves you will need to run install again)
2. `git clone https://github.com/marisabelmunoz/Bib-Title-Generator.git` It is important that you use git if you also want to get updates!
  - Else: download and extract the code to a permanent location where it will live. (If it moves you will need to run install again)
3. Right click inside the folder created and open the Terminal, inside the terminal type: `python install.py`
4. Wait for the dependencies to install.
5. Once the shortcut is created, **drag it to Desktop or taskbar** as you wish.
6. Double click and the browser will automatically open
7. For setting up the API, please read the **about** page.

See the About page for more information.

## Idea:

I have experience both with programming and guest satisfaction for the hotel industry. My role during the hotel days was to take feedback and improve the experience of both guests and colleagues. So I am always in search of optimization and excuses to play with code. 

As part of the adoption of AI in order to create more accurate bibliographic records, I realized we were all constantly asking AI models to generate the record based on a book at hand. We would then proceed to copy and paste line by line on our cataloguing system. The request from my colleague was "I wish I could just then send it to the catalogue". Which ignited the idea, "You can!"

## How does it work:

The script runs on a python flask server locally. 

#### install.py
- This script will create the shortcut which you can add to your desktop. 
#### app.py
- This is the main script, it will run the server and automatically open the browser for you.

#### application flow:
- User sets up the **configuration** before starting. The configuration is used for the API. You do not need to write your real name or contact, but this is used to identify the API used. So if there are issues, OCLC can find the requests and troubleshoot.
- On the **Bibliographic Record screen**, user selects what kind of record to create.
- On the **textbox** bellow the setup, user will add any information at hand
- On the **Extra Instructions** box, user can add more specific requests.
- User press `copy`
- On the chosen AI, user pastes the code.
- On the **API box**, user paste the result and send to Worldcat API.
- User is responsible for verifying accuracy and correcting mistakes.


## Todo
- [ ] [rda relators](https://help-nl.oclc.org/Metadata_Services/GGC/Richtlijnen/RDA_-_Resource_Description_and_Access/Relatiecodes_-_Algemene_inleiding/5.Engelse_en_Nederlandse_betekenis_van_relatiecodes_en_toelichting) - add to instructions to use this for person
- [X] Add profiles for the 008 so we can always use what we need (i.e. biofraphies should always have 23 = r, 34 = 1, 33 - 0, etc. )
- [x] Add the auto update via api (already tested)
