<?php
function sendTelegramMessage($botToken, $chatID, $mensagem)
{
    // URL da API do Telegram para enviar mensagens
    $url = "https://api.telegram.org/bot{$botToken}/sendMessage";

    // Dados que serão enviados via POST
    $dados = [
        'chat_id' => $chatID,
        'text' => $mensagem,
        'parse_mode' => 'HTML',
    ];

    // Inicializa o cURL
    $ch = curl_init();

    // Configura as opções do cURL
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, $dados);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

    // Executa a requisição e obtém a resposta
    $resposta = curl_exec($ch);

    // Verifica se houve erro
    $ret = "";
    if ($resposta === false) {
        $ret = curl_error($ch);
    }

    // Fecha a conexão cURL
    curl_close($ch);

    return $ret;
}
