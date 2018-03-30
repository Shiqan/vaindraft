// Copyright 2009 FriendFeed
//
// Licensed under the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License. You may obtain
// a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
// WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
// License for the specific language governing permissions and limitations
// under the License.

$(document).ready(function() {
    $(".hero-select").on("click", function() {
      if ($(this).hasClass("hero-highlight")) {
        newMessage($(this).data('hero'));
      } else {
        $(this).addClass("hero-highlight");
      }

      return false;
    })

    updater.start();
});

function newMessage(message) {
  updater.socket.send(message);
}

var updater = {
    socket: null,

    start: function() {
        // TODO get websocket url from backend
        var url = "ws://" + location.host + "/chatsocket/" + room + "/" + role + "/" + draft_style;
        updater.socket = new WebSocket(url);
        updater.socket.onmessage = function(event) {
            updater.showMessage(JSON.parse(event.data));
        }
    },

    showMessage: function(message) {
        if (message.type == "message") {
            // TODO toaster
            removeHeroHighlight();
        }
        
        else if (message.type == "update") {
            updateDraft(message.message, message.index);
        }
        
        else if (message.type == "history") {
            updateHistory(message.message);
        }
    }
};


function lockHero(hero) {
  $(hero).removeClass("hero-select hero-highlight").addClass("hero-locked").off("click");
}

function removeHeroHighlight() {
  $(".hero-select").removeClass("hero-highlight");
}

function updateDraft(hero, index) {
    var draft_item = $(".draft-item > img[data-order='"+index+"']");
    var hero_select = $(".hero-select[data-hero='"+hero+"']");
    
    $(draft_item).attr('src', '/static/images/heroes/'+hero+'.png');
    lockHero(hero_select);
}

function updateHistory(draftHistory) {
    for (let i of draftHistory) {
        updateDraft(i.message, i.index);
    }
}