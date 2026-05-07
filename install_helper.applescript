-- AbletonRPC Installer
-- Copies the app to /Applications and removes Gatekeeper restrictions in one step.

set appName to "AbletonRPC.app"
set dmgPath to (path to me as text)
-- Go up two levels from the installer app to find the DMG root
set dmgFolder to do shell script "dirname " & quoted form of POSIX path of dmgPath
set sourcePath to dmgFolder & "/" & appName
set destPath to "/Applications/" & appName

-- Confirm with user
display dialog "This will install AbletonRPC to your Applications folder and remove the Gatekeeper restriction so it opens without warnings." & return & return & "Your administrator password will be requested." buttons {"Cancel", "Install"} default button "Install" with icon note with title "Install AbletonRPC"

-- Run everything in one sudo call — single password prompt
try
    do shell script "
        # Remove existing install if present
        rm -rf " & quoted form of destPath & "
        
        # Copy app to Applications
        cp -R " & quoted form of sourcePath & " /Applications/
        
        # Remove quarantine flag
        xattr -rd com.apple.quarantine " & quoted form of destPath & "
        
        # Ad-hoc codesign so macOS is happy
        codesign --force --deep --sign - " & quoted form of destPath & "
    " with administrator privileges
    
    display dialog "✅ AbletonRPC has been installed successfully!" & return & return & "You can now open AbletonRPC from your Applications folder. Eject this disk image once you're done." buttons {"Open Applications Folder", "Done"} default button "Open Applications Folder" with icon note with title "Installation Complete"
    
    if button returned of result is "Open Applications Folder" then
        do shell script "open /Applications"
    end if

on error errMsg number errNum
    if errNum is -128 then
        -- User cancelled the password prompt — silently exit
        return
    end if
    display dialog "❌ Installation failed." & return & return & errMsg buttons {"OK"} default button "OK" with icon stop with title "Installation Failed"
end try
