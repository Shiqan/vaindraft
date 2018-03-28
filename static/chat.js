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
        lockHero(this);
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
        var url = "ws://" + location.host + "/chatsocket/" + room + "/" + role + "/" + draft_style;
        updater.socket = new WebSocket(url);
        updater.socket.onmessage = function(event) {
            updater.showMessage(JSON.parse(event.data));
        }
    },

    showMessage: function(message) {
        var draft_item = $(".draft-item > img[data-order='"+message.index+"']");
        var hero_select = $(".hero-select[data-hero='"+message.hero+"']");

        $(draft_item).attr('src', '/static/images/heroes/'+message.hero+'.png');
        lockHero(hero_select);
    }
};


function lockHero(element) {
  $(element).removeClass("hero-select hero-highlight").addClass("hero-locked").off("click");
}
