// ==UserScript==
// @name         D2JSP Batch Scraper
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Batch scrape D2JSP pages, saving to local server
// @author       You
// @match        https://forums.d2jsp.org/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      127.0.0.1
// @connect      localhost
// ==/UserScript==

(function() {
    'use strict';

    const SERVER_URL = 'http://127.0.0.1:8765';
    // Delay before scraping to ensure page loads and looks natural
    const IDLE_DELAY_MS = Number(GM_getValue('scraper_delay', 1500)); 
    
    // UI Panel setup
    const panel = document.createElement('div');
    panel.style.position = 'fixed';
    panel.style.top = '10px';
    panel.style.right = '10px';
    panel.style.backgroundColor = 'rgba(0,0,0,0.85)';
    panel.style.color = '#fff';
    panel.style.padding = '15px';
    panel.style.zIndex = '999999';
    panel.style.border = '1px solid #666';
    panel.style.borderRadius = '5px';
    panel.style.fontFamily = 'sans-serif';
    panel.style.fontSize = '12px';
    panel.style.boxShadow = '0 4px 6px rgba(0,0,0,0.3)';
    
    const title = document.createElement('strong');
    title.innerText = 'D2JSP Batch Scraper';
    panel.appendChild(title);
    panel.appendChild(document.createElement('br'));
    
    const statusTxt = document.createElement('span');
    statusTxt.innerText = 'Status: Idle';
    statusTxt.style.color = '#ccc';
    panel.appendChild(statusTxt);
    panel.appendChild(document.createElement('br'));
    
    const toggleBtn = document.createElement('button');
    toggleBtn.innerText = 'Start Scraper';
    toggleBtn.style.marginTop = '10px';
    toggleBtn.style.cursor = 'pointer';
    toggleBtn.style.padding = '5px 10px';
    toggleBtn.style.backgroundColor = '#4CAF50';
    toggleBtn.style.color = 'white';
    toggleBtn.style.border = 'none';
    toggleBtn.style.borderRadius = '3px';
    panel.appendChild(toggleBtn);
    
    document.body.appendChild(panel);
    
    let isRunning = GM_getValue('scraper_running', false);
    
    function updateUI() {
        toggleBtn.innerText = isRunning ? '🛑 Stop Scraper' : '▶️ Start Scraper';
        toggleBtn.style.backgroundColor = isRunning ? '#f44336' : '#4CAF50';
        if (!isRunning) {
            statusTxt.innerText = 'Status: Paused';
        }
    }
    updateUI();
    
    toggleBtn.addEventListener('click', () => {
        isRunning = !isRunning;
        GM_setValue('scraper_running', isRunning);
        updateUI();
        if (isRunning) {
            runScraperWorkflow();
        }
    });

    const CF_TITLE = "Just a moment...";
    
    function setStatus(msg) {
        statusTxt.innerText = `Status: ${msg}`;
        console.log(`[Scraper] ${msg}`);
    }

    function runScraperWorkflow() {
        if (!isRunning) return;
        
        setStatus(`Waiting ${IDLE_DELAY_MS}ms...`);
        
        setTimeout(() => {
            if (!isRunning) return;
            
            if (document.title.includes(CF_TITLE)) {
                setStatus('CF Challenge detected, waiting for resolution...');
                // we don't clear the running state, hopefully challenge passes and page reloads
                return;
            }
            
            // Check for potential errors that should halt the queue.
            const pageText = document.body.innerText;
            if (pageText.includes("You must be logged in")) {
                setStatus('Error: Not logged in. Stopping.');
                isRunning = false;
                GM_setValue('scraper_running', false);
                updateUI();
                return;
            }
            
            setStatus('Sending HTML to server...');
            
            const htmlContent = document.documentElement.outerHTML;
            const currentUrl = window.location.href;
            
            GM_xmlhttpRequest({
                method: "POST",
                url: SERVER_URL + "/save",
                data: JSON.stringify({ url: currentUrl, html: htmlContent }),
                headers: { "Content-Type": "application/json" },
                onload: function(response) {
                    if (response.status === 200) {
                        try {
                            const res = JSON.parse(response.responseText);
                            setStatus(`Saved. Remaining: ${res.remaining}`);
                            getNextUrl();
                        } catch (e) {
                            setStatus('Error parsing save response');
                        }
                    } else {
                        setStatus(`Save failed HTTP ${response.status}`);
                        isRunning = false;
                        GM_setValue('scraper_running', false);
                        updateUI();
                    }
                },
                onerror: function(err) {
                    setStatus('Connection to server failed. Is it running?');
                    isRunning = false;
                    GM_setValue('scraper_running', false);
                    updateUI();
                }
            });
            
        }, IDLE_DELAY_MS);
    }
    
    function getNextUrl() {
        if (!isRunning) return;
        
        setStatus('Fetching next URL...');
        GM_xmlhttpRequest({
            method: "GET",
            url: SERVER_URL + "/next",
            onload: function(response) {
                if (response.status === 200) {
                    try {
                        const res = JSON.parse(response.responseText);
                        if (res.url && res.url !== window.location.href) {
                            setStatus(`Navigating... (Q: ${res.remaining})`);
                            window.location.href = res.url;
                        } else if (res.url === window.location.href) {
                            // If same url, wait and try to get next again? No, the server should pop it.
                            setStatus('Server returned same URL. Trying again in 2s...');
                            setTimeout(getNextUrl, 2000);
                        } else {
                            setStatus('DONE. Queue empty.');
                            isRunning = false;
                            GM_setValue('scraper_running', false);
                            updateUI();
                        }
                    } catch(e) {
                        setStatus('Parse error on /next');
                    }
                } else {
                     setStatus(`/next failed HTTP ${response.status}`);
                }
            },
            onerror: function(err) {
                setStatus('Connection to server failed on /next');
                isRunning = false;
                GM_setValue('scraper_running', false);
                updateUI();
            }
        });
    }

    if (isRunning) {
        // Auto-start on load if active
        runScraperWorkflow();
    }
    
})();
