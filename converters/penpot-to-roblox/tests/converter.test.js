#!/usr/bin/env node
/**
 * Tests for the Penpot to Roblox converter
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'fs';
import { convertPenpotToRoblox } from '../dist/converter.js';

describe('Penpot to Roblox Converter', () => {
  test('converts HUD fixture', () => {
    const board = JSON.parse(readFileSync('fixtures/hud.json', 'utf-8'));
    const spec = convertPenpotToRoblox(board);
    
    assert.strictEqual(spec.version, '1.0.0');
    assert.strictEqual(spec.board.name, 'GameHUD');
    assert.strictEqual(spec.board.width, 1920);
    assert.strictEqual(spec.board.height, 1080);
    
    // Check HUD container
    assert.strictEqual(spec.elements.length, 1);
    const hud = spec.elements[0];
    assert.strictEqual(hud.name, 'HUD');
    assert.strictEqual(hud.type, 'Frame');
    
    // Check CoinCounter
    assert(hud.children);
    assert.strictEqual(hud.children.length, 1);
    const coinCounter = hud.children[0];
    assert.strictEqual(coinCounter.name, 'CoinCounter');
    assert.strictEqual(coinCounter.type, 'Frame');
    assert(coinCounter.corner);
    assert.strictEqual(coinCounter.corner.radius, 12);
    assert(coinCounter.stroke);
    assert.strictEqual(coinCounter.stroke.thickness, 2);
    
    // Check children (icon and text)
    assert(coinCounter.children);
    assert.strictEqual(coinCounter.children.length, 2);
    
    const icon = coinCounter.children[0];
    assert.strictEqual(icon.name, 'Icon');
    assert.strictEqual(icon.type, 'ImageLabel');
    assert(icon.image);
    assert.strictEqual(icon.image.contentHash.length, 16);
    
    const amount = coinCounter.children[1];
    assert.strictEqual(amount.name, 'Amount');
    assert.strictEqual(amount.type, 'TextLabel');
    assert.strictEqual(amount.text, '0');
    assert(amount.font);
    assert.strictEqual(amount.font.weight, 'Bold');
  });
  
  test('converts menu fixture', () => {
    const board = JSON.parse(readFileSync('fixtures/menu.json', 'utf-8'));
    const spec = convertPenpotToRoblox(board);
    
    assert.strictEqual(spec.board.name, 'MainMenu');
    assert.strictEqual(spec.elements.length, 1);
    
    const container = spec.elements[0];
    assert.strictEqual(container.name, 'MenuContainer');
    assert(container.children);
    assert.strictEqual(container.children.length, 3);
    
    const title = container.children[0];
    assert.strictEqual(title.name, 'Title');
    assert.strictEqual(title.type, 'TextLabel');
    assert.strictEqual(title.text, 'My Game');
    
    const playButton = container.children[1];
    assert.strictEqual(playButton.name, 'PlayButton');
    assert(playButton.children);
    const playText = playButton.children[0];
    assert.strictEqual(playText.type, 'TextLabel');
    assert.strictEqual(playText.text, 'PLAY');
    
    const settingsButton = container.children[2];
    assert.strictEqual(settingsButton.name, 'SettingsButton');
  });
  
  test('converts shop grid fixture', () => {
    const board = JSON.parse(readFileSync('fixtures/shop.json', 'utf-8'));
    const spec = convertPenpotToRoblox(board);
    
    assert.strictEqual(spec.board.name, 'ShopGrid');
    
    const shop = spec.elements[0];
    assert.strictEqual(shop.name, 'Shop');
    assert(shop.layout);
    assert.strictEqual(shop.layout.type, 'Grid');
    
    assert(shop.children);
    const item = shop.children[0];
    assert.strictEqual(item.name, 'Item1');
    assert(item.aspectRatio);
    assert(item.children);
    assert.strictEqual(item.children.length, 3);
    
    const itemImage = item.children[0];
    assert.strictEqual(itemImage.type, 'ImageLabel');
    
    const itemName = item.children[1];
    assert.strictEqual(itemName.type, 'TextLabel');
    assert.strictEqual(itemName.text, 'Sword');
    
    const itemPrice = item.children[2];
    assert.strictEqual(itemPrice.text, '100 coins');
  });
  
  test('handles button detection', () => {
    const board = {
      id: 'test',
      name: 'Test',
      children: [
        {
          id: 'btn1',
          name: 'SubmitButton',
          type: 'frame',
          children: [
            { id: 'txt', name: 'Text', type: 'text', content: 'Submit' }
          ]
        }
      ]
    };
    
    const spec = convertPenpotToRoblox(board);
    const button = spec.elements[0].children[0];
    assert.strictEqual(button.type, 'TextLabel'); // Parent frame, child is text
  });
  
  test('handles font mapping', () => {
    const board = {
      id: 'test',
      name: 'Test',
      children: [
        {
          id: 't1',
          name: 'Text1',
          type: 'text',
          content: 'Hello',
          fontFamily: 'Inter',
          fontWeight: '700'
        },
        {
          id: 't2',
          name: 'Text2',
          type: 'text',
          content: 'World',
          fontFamily: 'Roboto Mono',
          fontWeight: '400'
        }
      ]
    };
    
    const spec = convertPenpotToRoblox(board);
    
    const text1 = spec.elements[0];
    assert(text1.font);
    assert.strictEqual(text1.font.family, 'BuilderSans');
    assert.strictEqual(text1.font.weight, 'Bold');
    
    const text2 = spec.elements[1];
    assert(text2.font);
    assert.strictEqual(text2.font.family, 'RobotoMono');
    assert.strictEqual(text2.font.weight, 'Regular');
  });
  
  test('handles scale-based positioning', () => {
    const board = {
      id: 'test',
      name: 'Test',
      width: 1000,
      height: 1000,
      children: [
        {
          id: 'elem',
          name: 'Element',
          type: 'rect',
          x: 100,
          y: 200,
          width: 300,
          height: 400
        }
      ]
    };
    
    const spec = convertPenpotToRoblox(board);
    const elem = spec.elements[0];
    
    assert.strictEqual(elem.position.scaleX, 0.1);
    assert.strictEqual(elem.position.scaleY, 0.2);
    assert.strictEqual(elem.size.scaleX, 0.3);
    assert.strictEqual(elem.size.scaleY, 0.4);
  });
  
  test('generates warnings for unsupported features', () => {
    const board = {
      id: 'test',
      name: 'Test',
      children: [
        {
          id: 'elem',
          name: 'Element',
          type: 'rect',
          strokes: [
            { color: '#FF0000', width: 2 },
            { color: '#00FF00', width: 1 }
          ]
        }
      ]
    };
    
    const spec = convertPenpotToRoblox(board);
    assert(spec.warnings.length > 0);
    assert(spec.warnings.some(w => w.includes('multiple strokes')));
  });
});
