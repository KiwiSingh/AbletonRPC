# AbletonRPC
![AbletonRPC logo](https://i.ibb.co/V9NbLcY/ableton-image-beeg.png)

Unofficial Ableton Live Discord rich presence for macOS

## DISCLAIMER 
This experimental rich presence client is self-hosted (i.e. on your own Discord developer portal) and making some rudimentary modifications to your Ableton Live installation. On macOS, applications are actually directories, with a runner to execute any code - along with the assets needed to execute said code - inside that directory. If this is something you are not comfortable with, or have no idea what the heck you're doing, please stop here.

## Stuff needed

1. Existing Discord account
2. Any Discord client (preferably the official one, pls; let's keep it halal thanks 🙏)
3. Account on the Discord Developer Portal
4. An IDE to edit code
5. Ableton Live 12 Suite (this \*might\* work on Live 11 and Live 10 Suite with some minor tweaking, but I only have 12, so ymmv)
6. A functioning brain 🧠

## Instructions
1. Clone this repo using 

```zsh
git clone https://github.com/KiwiSingh/AbletonRPC
```
2. Create a new application on your Discord Developer Portal, and fill in the deets as per the screenshots below.

![1](https://i.ibb.co/PNfY9nD/Discord-Ded1.png)
![2](https://i.ibb.co/gMfKK06/Discord-Ded2.png)

3. Close Ableton Live in case it is open (obv. save any unsaved projects first)
4. Inside your Applications folder (or external drive, if you're a madlad who installed Ableton on an external SSD for some reason), right click `Ableton Live 12 Suite.app` and navigate to `/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/MIDI Remote Scripts`.
5. Inside the `MIDI Remote Scripts` folder paste the `FauxMIDI` folder from this repo.
6. Modify the `log_file_path = "/Volumes/Charidrive/rpctemp/CurrentProjectLog.txt"` line so that the value of `log_file_path` represents a path on your own system.
6a. In case the script throws any errors in stdout, create or delete said log file accordingly.
7. Inside of Terminal, navigate to the `FauxMIDI` folder and give read, write and execute permissions to the MIDI remote script. `chmod +rwx` the entire directory if needed.
8. Open up Ableton Live, and set up the `FauxMIDI` device which will interface with your Discord application, as per the below screenshot.

![MIDI](https://i.ibb.co/9pbMpW1/Ableton-MIDIprefs.png)

10. Create a new Python 3 virtual environment so that you don't bork up your existing install. Install the reqs needed by `abletonrpc.py` using

    ```zsh
    pip install -r requirements.txt
    ```
    or
    ```
    pip3 install -r requirements.txt
    ```
    
12. Open up the `abletonrpc.py` and replace the placeholder in `client_id = "Your Client ID"  # Replace with your actual client ID` with your actual client ID.
13. `chmod +x` the `abletonrpc.py` script
14. Fire up Discord if you haven't already. Remove Invisible status if enabled
15. Run `python abletonrpc.py` or `python3 abletonrpc.py`
16. Enjoy!


## Frequently asked questions
**Q.** Is this a port of DawRPC?
**A.** No, it is not. I wanted to make a port of DAWRPC, but since I only have Ableton Live and Studio One to experiment with, not to mention the fact that I would have to effectively reverse engineer a ton of Windows DLL and f*ck around in C#, I dropped the idea (at least for the timebeing).
**Q.** I get a `ModuleNotFound` error. Help!
**A.** This is most likely because you have not correctly initialized a virtual environment. Restart your shell if you have already installed all requirements.
**Q.** VS Code won't let me edit your Python script!
**A.** Refer to the answer above.
**Q.** Can I make a Discord bot/plugin/other self-hosted instance using this?
**A.** Sure. Go crazy. It's FOSS. Though please note that I do not condone using modified Discord clients, and if you end up getting into any trouble because of a plugin/self-bot, I am not liable. But since this project is FOSS, I cannot stop anyone from forking it and doing with it as they please.
**Q.** Is this safe? Will I mess up my Ableton install?
**A.** If you know what you're doing, this is completely safe. If you do not feel comfortable with such an involved solution, please look elsewhere.
**Q.** Where do I contact you regarding questions about this project?
**A.** You may reach out to my email address at [kiwisingh@proton.me](mailto:kiwisingh@proton.me)



