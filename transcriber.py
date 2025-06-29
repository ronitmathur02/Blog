import os
import time
import base64
import subprocess
import speech_recognition as sr

def record_audio(duration, output_file="meeting_audio.webm", driver=None):
    """Record audio from Google Meet with improved permission handling."""
    print(f"Starting to capture Google Meet audio for {duration} seconds...")
    
    if not driver:
        print("ERROR: No browser driver provided, can't capture meeting audio")
        return None
        
    try:
        # Clear any previous recording state
        driver.execute_script("""
            if (window.meetRecorder) {
                try {
                    if (window.meetRecorder.state === 'recording') {
                        window.meetRecorder.stop();
                    }
                } catch(e) {}
            }
            
            window.audioChunks = [];
            console.log("Recording state cleared");
        """)
        
        # Setup screen capture with audio - with better permission handling
        print("⚠️ IMPORTANT: You will see a permission dialog.")
        print("✅ Please SELECT THE GOOGLE MEET TAB and CHECK 'SHARE AUDIO' option!")
        print("⏱️ Waiting 20 seconds for you to approve permissions...")
        
        started = driver.execute_script("""
            // Create global variable to track permission status
            window.permissionStatus = 'waiting';
            
            window.startMeetRecording = async function() {
                try {
                    console.log("Requesting display capture with audio...");
                    
                    // Force a more visible prompt that clearly shows audio option
                    const displayMediaOptions = {
                        video: {
                            displaySurface: "browser",  // Prefer browser tab
                            logicalSurface: true,
                            cursor: "never"
                        },
                        audio: {
                            echoCancellation: true,     // Reduce echo
                            noiseSuppression: true,     // Reduce background noise
                            autoGainControl: true       // Normalize audio levels
                        },
                        preferCurrentTab: true,         // Prefer current tab if available
                        selfBrowserSurface: "include"   // Include browser surface
                    };
                    
                    // This will show the permission dialog
                    const stream = await navigator.mediaDevices.getDisplayMedia(displayMediaOptions);
                    
                    // Specifically check if we have audio tracks
                    const audioTracks = stream.getAudioTracks();
                    console.log("Audio tracks:", audioTracks.length);
                    
                    if (!audioTracks || audioTracks.length === 0) {
                        window.permissionStatus = 'no-audio';
                        console.error("❌ No audio tracks found - did you select 'Share audio'?");
                        stream.getTracks().forEach(track => track.stop());
                        return false;
                    }
                    
                    // Log audio track info for debugging
                    audioTracks.forEach((track, i) => {
                        console.log(`Audio track ${i}:`, track.label, track.enabled, track.readyState);
                    });
                    
                    // Create media recorder with optimal settings for speech
                    window.meetRecorder = new MediaRecorder(stream, {
                        mimeType: 'audio/webm;codecs=opus',
                        audioBitsPerSecond: 128000
                    });
                    
                    // Set up data handler
                    window.audioChunks = [];
                    window.meetRecorder.ondataavailable = (event) => {
                        if (event.data && event.data.size > 0) {
                            window.audioChunks.push(event.data);
                            console.log(`Recorded chunk: ${event.data.size} bytes`);
                        }
                    };
                    
                    // Start recording with 1-second chunks
                    window.meetRecorder.start(1000);
                    console.log("✅ Recording started successfully");
                    window.permissionStatus = 'success';
                    return true;
                } catch (e) {
                    console.error("Recording setup error:", e);
                    window.permissionStatus = 'error';
                    return false;
                }
            };
            
            // Start the recording process that will trigger the permission dialog
            window.startMeetRecording();
            
            // Return immediately - we'll check status later
            return 'dialog-shown';
        """)
        
        # Wait for user to interact with the permission dialog
        print("Chrome is displaying a permissions dialog. Please interact with it.")
        wait_time = 20
        for i in range(wait_time):
            time.sleep(1)
            print(f"Waiting for permissions: {wait_time - i} seconds remaining...")
            
            # Check if permission was granted
            status = driver.execute_script("return window.permissionStatus;")
            if status == 'success':
                print("✅ Permission granted! Recording started.")
                break
            elif status == 'no-audio':
                print("❌ Permission granted but 'Share audio' was NOT selected!")
                return None
            elif status == 'error':
                print("❌ Permission request failed or was denied.")
                return None
        
        # Check final status after wait
        status = driver.execute_script("return window.permissionStatus;")
        if status != 'success':
            print("❌ Permissions were not properly granted in the time allowed.")
            return None
            
        # If we got here, recording has started successfully
        # Record for the specified duration
        print(f"Recording for {min(duration, 60)} seconds...")
        for i in range(min(duration, 60)):
            if i % 5 == 0:
                chunks = driver.execute_script("return window.audioChunks ? window.audioChunks.length : 0")
                print(f"Recording in progress... {i}/{min(duration, 60)}s ({chunks} chunks)")
            time.sleep(1)
        
        # Stop recording and get the audio data
        print("Stopping recording and collecting audio data...")
        audio_data = driver.execute_script("""
            return new Promise((resolve) => {
                if (!window.meetRecorder || window.meetRecorder.state === 'inactive') {
                    console.error("No active recorder found");
                    resolve(null);
                    return;
                }
                
                // Handle the stop event
                window.meetRecorder.onstop = () => {
                    console.log("Recorder stopped");
                    
                    if (!window.audioChunks || window.audioChunks.length === 0) {
                        console.error("No audio chunks recorded");
                        resolve(null);
                        return;
                    }
                    
                    console.log(`Total chunks: ${window.audioChunks.length}`);
                    
                    // Create audio blob
                    const audioBlob = new Blob(window.audioChunks, { type: 'audio/webm' });
                    console.log(`Audio blob size: ${audioBlob.size} bytes`);
                    
                    // Convert to base64
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = () => {
                        const base64data = reader.result.split(',')[1];
                        resolve(base64data);
                    };
                };
                
                // Stop the recorder
                window.meetRecorder.stop();
                
                // Clean up
                if (window.meetRecorder.stream) {
                    window.meetRecorder.stream.getTracks().forEach(track => track.stop());
                }
            });
        """)
        
        if not audio_data:
            print("ERROR: No audio data was captured")
            return None
        
        # Save the audio data
        with open(output_file, 'wb') as f:
            f.write(base64.b64decode(audio_data))
        
        file_size = os.path.getsize(output_file) / 1024
        print(f"Successfully saved {file_size:.1f}KB of audio to {output_file}")
        
        # Return the path to the saved file
        return output_file
        
    except Exception as e:
        print(f"Error in audio capture: {e}")
        return None

def convert_audio_with_ffmpeg(input_file, output_file=None):
    """Convert audio to WAV format using FFmpeg with enhanced settings."""
    if not output_file:
        output_file = os.path.splitext(input_file)[0] + ".wav"
        
    print(f"Converting {input_file} to {output_file} using FFmpeg...")
    
    try:
        # Run FFmpeg with optimized settings for speech clarity
        subprocess.run([
            "ffmpeg",
            "-i", input_file,           # Input file
            "-y",                       # Overwrite output without asking
            "-acodec", "pcm_s16le",     # Output codec (standard for WAV)
            "-ar", "16000",             # Sample rate (16kHz is good for speech)
            "-ac", "1",                 # Convert to mono
            "-af", "highpass=f=200,lowpass=f=3000",  # Filter to focus on speech frequencies
            output_file
        ], check=True, capture_output=True)
        
        print(f"Conversion successful: {os.path.getsize(output_file)/1024:.1f}KB WAV file created")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg conversion failed: {e}")
        print(f"FFmpeg stderr: {e.stderr.decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Error in audio conversion: {e}")
        return None

def transcribe_audio(audio_file):
    """Transcribe audio file to text using Google Speech Recognition."""
    if not audio_file or not os.path.exists(audio_file):
        print("ERROR: No audio file to transcribe")
        return ""
    
    # If file is WebM, convert to WAV first using FFmpeg
    if audio_file.endswith(".webm"):
        wav_file = convert_audio_with_ffmpeg(audio_file)
        if not wav_file:
            print("ERROR: Could not convert WebM to WAV")
            return ""
        audio_file = wav_file
    
    file_size = os.path.getsize(audio_file) / 1024
    print(f"Transcribing audio file: {audio_file} ({file_size:.1f}KB)")
    
    # Skip if file is too small to contain meaningful audio
    if file_size < 5:
        print("ERROR: Audio file too small to contain speech")
        return ""
    
    # Transcribe using Google Speech Recognition
    try:
        recognizer = sr.Recognizer()
        
        # Use longer phrases for better context
        recognizer.pause_threshold = 1.0
        
        print("Starting transcription with Google Speech Recognition...")
        with sr.AudioFile(audio_file) as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source)
            # Get audio data
            audio_data = recognizer.record(source)
            
        # Try multiple language options if first attempt fails
        transcript = ""
        try:
            transcript = recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            print("Retrying with explicit language setting...")
            try:
                transcript = recognizer.recognize_google(audio_data, language="en-US")
            except sr.UnknownValueError:
                print("Speech recognition could not understand audio")
        
        if transcript:
            print(f"Transcription successful: {len(transcript)} characters")
        else:
            print("No speech detected in the audio")
            
        return transcript
            
    except Exception as e:
        print(f"Error in transcription: {e}")
        return ""

def record_and_transcribe(duration, driver=None):
    """Record Google Meet audio and transcribe it, with fallback options."""
    print(f"Starting recording process for {duration} seconds...")
    
    # Save files with timestamps to avoid overwriting
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    audio_file = os.path.join(os.getcwd(), f"meet_audio_{timestamp}.webm")
    
    try:
        # Try browser audio capture first
        print("Attempting browser audio capture...")
        captured_file = record_audio(duration, audio_file, driver)
        
        # If browser capture fails, try fallback methods
        if not captured_file or not os.path.exists(captured_file):
            print("Browser audio capture failed, trying fallback method...")
            
            # Install pyaudio with: pip install pyaudio
            try:
                import pyaudio
                fallback_file = os.path.join(os.getcwd(), f"fallback_audio_{timestamp}.wav")
                captured_file = fallback_record_audio(duration, fallback_file)
            except ImportError:
                print("pyaudio not installed, can't use fallback recording")
                captured_file = None
        
        if not captured_file or not os.path.exists(captured_file):
            print("All audio capture methods failed")
            return ""
        
        # Convert and transcribe the audio
        transcript = transcribe_audio(captured_file)
        
        # Return the transcript
        return transcript
        
    except Exception as e:
        print(f"ERROR in recording/transcription process: {e}")
        return ""

def fallback_record_audio(duration, output_file="fallback_audio.wav"):
    """Fallback method to record system audio using microphone."""
    try:
        import pyaudio
        import wave
        
        print("Using fallback microphone recording...")
        
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        
        print(f"Recording from microphone for {duration} seconds...")
        frames = []
        
        # Record for specified duration
        for i in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)
            if i % (5 * RATE // CHUNK) == 0:
                print(f"Microphone recording in progress... {i/(RATE//CHUNK)} seconds")
        
        print("Microphone recording complete.")
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Save to WAV file
        wf = wave.open(output_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        print(f"Fallback recording saved to {output_file}")
        return output_file
        
    except Exception as e:
        print(f"Fallback recording failed: {e}")
        return None
