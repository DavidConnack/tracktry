# TrackTry-Custom Component
 A component to integrate TrackTry into Home Assistant
 
 You will need to get an API key from tracktry.com
 
 All carrier codes can be found on their website.
 
 Two possibilities for installation :

Manually : add the "tracktry" folder to the /config/custom_components folder ; reboot

With HACS : go in HACS, click on Integrations, click on the three little dots at top of the screen and selection "custom repositories", add this github url, select "Integration" as repository, and click ADD.

Then go to the Integrations tab of HACS, and install the "TrackTry" integration.
 
Add to configuration.yml

sensor:
    - platform: tracktry
      api_key: <key>
