# Examples Used in Prompting Methods

## LATO

### Key Activity Identification
```
Input:
The device at startup should first perform user account authentication, verifying the validity and legality of the user account. If the user account is invalid or unrecognized, prompt the user and block further operations. After authentication succeeds, the device should initiate a multi-factor authentication process (e.g., password, fingerprint, facial recognition), requiring at least two methods to pass according to the user’s configured security level. Each authentication step should include timeout and error-handling mechanisms; if multiple failures occur (e.g., more than three attempts), the device should lock the user account and issue a warning notification. Upon successful authentication, the device should record detailed information about the authentication event—including time, authentication method, and result—for later security review and log analysis. The device should periodically re-verify the user’s identity, especially when abnormal behavior is detected or after extended inactivity, to ensure continuous security.

Output:
[user account authentication, prompt user, abort operation, initiate multi-factor authentication, password authentication, fingerprint authentication, facial recognition, record passed methods, timeout and error handling, lock user account, issue warning notification, record authentication event details, periodic re-authentication]

Input:
When a user attempts to enter the system, they must first swipe their card for identity verification. If the card is invalid, the system will deny access and terminate the process; if the card is valid, the system will turn on the lights and start the air conditioning (AC), then execute the subsequent steps in parallel. Based on current temperature conditions, the system will adjust as follows: if it is hot, close the blinds and set the AC to high fan speed; if normal, set the AC to medium fan speed; if cloudy, turn off the AC and open the blinds. While monitoring temperature, the system also activates the environmental sensor for real-time monitoring of smoke. If smoke is detected, the system performs these parallel operations: open the door for rapid evacuation and generate an alarm to alert the user. If no smoke is detected, the system enters sleep mode.

Output:
[user attempts entry, card swipe authentication, deny access, terminate process, turn on lights, start AC, monitor temperature, close blinds, set AC to high speed, set AC to medium speed, turn off AC, open blinds, activate environmental sensor, monitor smoke, open door, allow rapid evacuation, generate alarm, alert user, enter sleep mode]
```

### Layerwise Relation Extraction
```
Input:
The device at startup should first perform user account authentication, verifying the validity and legality of the user account. If the user account is invalid or unrecognized, prompt the user and block further operations. After authentication succeeds, the device should initiate a multi-factor authentication process (e.g., password, fingerprint, facial recognition), requiring at least two methods to pass according to the user’s configured security level. Each authentication step should include timeout and error-handling mechanisms; if multiple failures occur (e.g., more than three attempts), the device should lock the user account and issue a warning notification. Upon successful authentication, the device should record detailed information about the authentication event—including time, authentication method, and result—for later security review and log analysis. The device should periodically re-verify the user’s identity, especially when abnormal behavior is detected or after extended inactivity, to ensure continuous security.

Final Output:
Level 1{
**user account authentication** triggers a conditional structure with 2 branches:
  Branch **user account invalid or unrecognized**: prompt user -> abort operation -> end
  Branch **user account authentication successful**: initiate multi-factor authentication -> [**initiate multi-factor authentication** triggers loop structure] -> authentication success -> record detailed authentication event information -> periodic re-authentication}
Level 2{
**Initiate multi-factor authentication** triggers a loop structure with the loop condition **number of passed authentication methods < 2**:
  [**number of passed authentication methods** triggers parallel structure] -> [**number of authentication failures** triggers conditional structure]}
Level 3{
**Number of passed authentication methods** triggers a parallel structure with 3 branches:
  Branch 1: password verification -> [**password verification** triggers conditional structure]
  Branch 2: fingerprint verification -> [**fingerprint verification** triggers conditional structure]
  Branch 3: facial recognition -> [**facial recognition** triggers conditional structure]
**Number of authentication failures** triggers a conditional structure with 1 branch:
  Branch **authentication failures > 3**: lock user account -> send warning notification -> end}
Level 4{
**Password verification** triggers a conditional structure with 2 branches:
  Branch **authentication success**: record authentication method
  Branch **authentication failure**: timeout and error handling -> authentication failures +1
**Fingerprint verification** triggers a conditional structure with 2 branches:
  Branch **authentication success**: record authentication method
  Branch **authentication failure**: timeout and error handling -> authentication failures +1
**Facial recognition** triggers a conditional structure with 2 branches:
  Branch **authentication success**: record authentication method
  Branch **authentication failure**: timeout and error handling -> authentication failures +1}
```

### Behaviroal Model Constructor
```
Input:
The device, upon startup, should first perform user account authentication, verifying the validity and legitimacy of the user account. If the user account is invalid or unrecognized, it should prompt the user and abort any further operations. Once authentication succeeds, the device should initiate a multi-factor authentication process (e.g., password, fingerprint, facial recognition), requiring at least two authentication methods to pass based on the user’s configured security level. Each authentication step should include timeout and error-handling mechanisms; if authentication fails multiple times (e.g., more than 3 times), the device should lock the user account and send a warning notification. After successful authentication, the device should log detailed information about the authentication event, including the time, methods used, and result, for subsequent security review and log analysis. The device should periodically re-verify the user’s identity, especially when abnormal behavior is detected or after long periods of inactivity, to ensure continuous security.

#Activity Identification
user account authentication, prompt user, abort operation, initiate multi-factor authentication, password recognition, fingerprint recognition, facial recognition, record successful authentication method, timeout and error handling, lock user account, send warning notification, authentication successful, log authentication event details, periodic re-authentication

#Relation Decomposition
Level 1{
**user account authentication** triggers a conditional structure, with 2 branches:
  Branch **user account invalid or unrecognized**: prompt user -> abort operation -> end
  Branch **user account authenticated successfully**: initiate multi-factor authentication -> [**initiate multi-factor authentication** triggers a loop structure] -> authentication successful -> log authentication event details -> periodic re-authentication}
Level 2{
**Initiate multi-factor authentication** triggers a loop structure, looping while **number of passed authentication methods < 2**:
  [**number of passed authentication methods** triggers a parallel structure] -> [**authentication failure count** triggers a conditional structure]}

Please understand the decomposition above and write a Information Integration, ensuring necessary descriptive details remain consistent with the input text.

Output:
user account authentication
if user account invalid/unrecognized
    prompt user
    abort operation
else
    initiate multi-factor authentication
    while number of passed authentication methods < 2
        fork
            password recognition
            if authentication successful
                record successful authentication method
            else
                timeout and error handling
                authentication failure count + 1
        fork
            fingerprint recognition
            if authentication successful
                record successful authentication method
            else
                timeout and error handling
                authentication failure count + 1
        fork
            facial recognition
            if authentication successful
                record successful authentication method
            else
                timeout and error handling
                authentication failure count + 1
        if authentication failure count > 3
            lock user account
            send warning notification
            end
    authentication successful
    log authentication event details
    periodic re-authentication
```

## Few-shot
```
Input:
When the device powers on, it should first perform user account authentication to verify the user account’s validity and legitimacy. If the user account is invalid or unrecognized, prompt the user and block further operations. After authentication succeeds, the device should initiate a multi-factor authentication flow (such as password, fingerprint, facial recognition), requiring at least two authentication methods to pass according to the user’s configured security level. Each authentication step should include timeout and error-handling mechanisms; if multiple authentication failures occur (e.g., more than 3 times), the device should lock the user’s account and issue a warning notification. Upon successful authentication, the device should log detailed information about the authentication event—including timestamp, authentication method, and result—for subsequent security review and log analysis. The device should periodically re-verify the user’s identity, especially when detecting anomalous behavior or prolonged inactivity, to ensure continuous security.

Please generate the PlantUML code for the activity diagram based on the above requirements. Output the result directly without explanation.

Output:
start
  :Perform user account authentication;
  if (user account valid?) then (yes)
     :Initiate multi-factor authentication;
     :Select authentication methods;
	 repeat
	   fork
	     :Enter password;
	     if (Password correct?) then (yes)
	       :Log authentication details;
	     else (no)
	       :Handle timeout and errors;
	     endif
	   fork again
	     :Scan fingerprint;
	     if (Fingerprint match?) then (yes)
	       :Log authentication details;
	     else (no)
	       :Handle timeout and errors;
	     endif
	   fork again
	     :Facial recognition;
	     if (Face recognition passed?) then (yes)
	       :Log authentication details;
	     else (no)
	       :Handle timeout and errors;
	     endif
	   end fork
	   if (Failure count > 3) then (yes)
	     :Lock account;
	     :Issue warning notification;
	     stop
	   else (no)
	     :Continue authentication;
	   endif
	 repeat while (At least two methods succeeded)
	 :Authentication successful;
	 :Log authentication event;
	else (no)
	 :Prompt invalid user account;
	 stop
	endif
	:Periodically re-verify;
	stop
```
