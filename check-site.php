<?php

$data = [];
$url = filter_input(INPUT_GET, "url", FILTER_SANITIZE_URL);
$title = filter_input(INPUT_GET, "title", FILTER_SANITIZE_FULL_SPECIAL_CHARS);
$body = filter_input(INPUT_GET, "body", FILTER_SANITIZE_SPECIAL_CHARS);

$data["status"] = "";
$data["message"] = "";
$data["title"] = "";
$data["title_check"] = "";
$data["body"] = "";

$headers = @get_headers($url);
$data["headers"] = $headers;
if ($headers && strpos($headers[0], '200')) {

    $html = file_get_contents($url);
    if ($html === false) {
        $data["status"] = "error";
        $data["message"] = "❌ erro ao acessar url";
    } else {
        $data["status"] = "success";
        $data["message"] = "✔️ validado";

        preg_match("/<title>(.*?)<\/title>/i", $html, $matches);
        if ($title <> "") {
            $data["title_check"] = "❌";
            if (isset($matches[1])) {
                $data["title"] = $matches[1];
                if (strpos(strtolower($data["title"]), strtolower($title)) !== false) {
                    $data["title_check"] = "✔️";
                } else {
                    $data["title_check"] = "❌";
                }
            }
        } elseif ($body <> "") {
            if (strpos(strtolower($html), strtolower($body)) !== false) {
                $data["title_check"] = "✔️";
            } else {
                $data["title_check"] = "❌";
            }
        } else {
            $data["title_check"] = "❗️";
        }
    }
} else {
    $data["status"] = "error";
    $data["message"] = "❌ site indisponível";
}

echo json_encode($data);
